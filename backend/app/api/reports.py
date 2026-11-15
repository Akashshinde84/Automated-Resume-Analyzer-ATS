"""Authenticated, non-persistent downloads from one authorized analysis source."""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from app.api.analyses import repository
from app.schemas.analysis import AnalysisResponse
from app.schemas.reports import AnalysisReport, ReportMatch, ReportRequest
from app.services.report_receipts import InvalidReportSnapshot, ReportReceipts, analysis_data
from app.services.reports import PDFReport

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.post("/reports", response_class=Response, summary="Download one authorized analysis and optional comparison",
             responses={200: {"description": "Private attachment; never stored by the report service.", "model": AnalysisReport,
                              "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}})
async def download_report(payload: ReportRequest, request: Request):
    receipts = ReportReceipts(request.app.state.settings)
    repo = repository(request) if payload.analysis_id else None
    if repo:
        detail = await run_in_threadpool(repo.get, payload.analysis_id, 1, 0)
        analysis = AnalysisResponse.model_validate(analysis_data(detail))
    else:
        analysis = payload.snapshot
        try:
            receipts.verify_analysis(analysis)
        except InvalidReportSnapshot:
            raise HTTPException(409, detail={"code": "invalid_report_snapshot", "message": "The analysis snapshot is changed or expired. Analyze the resume again before downloading."}) from None
    selected = None
    if payload.match_id:
        stored = await run_in_threadpool(repo.get_match, payload.analysis_id, payload.match_id)
        selected = ReportMatch(id=stored.id, job_description=stored.job_description, result=stored.result)
    elif payload.match:
        try:
            if payload.match.analysis_id != analysis.id:
                raise InvalidReportSnapshot()
            receipts.verify_match(payload.match, analysis.parsed.text, payload.job_description)
        except InvalidReportSnapshot:
            raise HTTPException(409, detail={"code": "invalid_report_snapshot", "message": "The comparison does not match this analysis, or it has expired. Run the comparison again."}) from None
        selected = ReportMatch(job_description=payload.job_description, result=payload.match.result)
    report = AnalysisReport(generated_at=datetime.now(timezone.utc),
                            analysis=AnalysisResponse.model_validate(analysis_data(analysis)), match=selected)
    headers = {"Content-Disposition": f'attachment; filename="resume-analysis.{payload.format}"',
               "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    if payload.format == "json":
        value = report.model_dump(mode="json", exclude={"analysis": {"report_token"}})
        return Response(json.dumps(value, ensure_ascii=False, indent=2), media_type="application/json", headers=headers)
    try:
        content = await run_in_threadpool(lambda: PDFReport().render(report))
    except Exception:
        raise HTTPException(503, detail={"code": "report_unavailable", "message": "The PDF could not be generated. Retry or download the JSON report."}) from None
    return Response(content, media_type="application/pdf", headers=headers)
