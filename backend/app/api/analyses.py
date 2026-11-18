"""Integrated single-user APIs. Persistence is opt-in, ownership is server-defined."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.api.resumes import read_resume_upload
from app.db.repository import AnalysisRepository
from app.schemas.analysis import AnalysisDetail, AnalysisPage, AnalysisResponse, JobMatchRequest, JobMatchResponse, ParsedResumeData
from app.schemas.candidate import ExtractionRequest
from app.services.extraction import InformationExtractor
from app.services.extraction.ner import SpacyNER
from app.services.diagnostics import failure_reference
from app.services.matching import MatchingService
from app.services.report_receipts import ReportReceipts
from app.services.readiness import ReadinessService

router = APIRouter(prefix="/api/v1", tags=["analyses"])


def repository(request):
    if request.app.state.settings.app_mode == "anonymous":
        raise HTTPException(403, detail={"code": "private_history_disabled", "message": "Anonymous processing cannot read or save stored analyses."})
    database = request.app.state.database
    if not request.app.state.settings.storage_enabled or database is None:
        raise HTTPException(409, detail={"code": "storage_disabled", "message": "Persistent storage is disabled; use stateless analysis or matching."})
    return AnalysisRepository(database, request.app.state.settings)


UPLOAD_SCHEMA = {"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
    "type": "object", "required": ["file"], "additionalProperties": False,
    "properties": {"file": {"type": "string", "format": "binary"},
                   "phone_region": {"type": "string", "description": "Optional supported two-letter phone region; no inferred default."}}
}}}}}


@router.post("/resumes/analyze", response_model=AnalysisResponse, openapi_extra=UPLOAD_SCHEMA,
             summary="Analyze one PDF/DOCX; save only with explicit store=true")
async def analyze(request: Request, store: bool = Query(False)):
    repo = repository(request) if store else None
    parsed, region = await read_resume_upload(request, allow_phone_region=True)
    if len(parsed["text"]) > 100_000:
        raise HTTPException(413, detail={"code": "extracted_text_limit", "message": "Extracted text exceeds the integrated analysis limit."})
    try:
        validated = ExtractionRequest(text=parsed["text"], phone_region=region)
    except ValidationError:
        raise HTTPException(422, detail={"code": "invalid_phone_region", "message": "Use a supported two-letter phone region or omit it."}) from None
    settings = request.app.state.settings
    try:
        extractor = InformationExtractor(SpacyNER(settings.spacy_model))
        extracted = await run_in_threadpool(extractor.extract, validated.text, validated.phone_region,
                                            parsed.get("hyperlinks"), parsed.get("layout_blocks"))
    except Exception as exc:
        reference = failure_reference("candidate_extraction", exc)
        raise HTTPException(500, detail={"code": "extraction_failed", "message": "Candidate analysis failed unexpectedly. Retry Analysis or contact the operator.", "diagnostic_id": reference}) from None
    if settings.require_ner_model and extracted.nlp.status != "available":
        raise HTTPException(503, detail={"code": "model_unavailable", "message": "The configured required NER model is unavailable."})
    result = AnalysisResponse(created_at=datetime.now(timezone.utc), parsed=ParsedResumeData.model_validate(parsed), extraction=extracted)
    result.readiness = await run_in_threadpool(ReadinessService(settings.readiness_weights).evaluate, result.parsed, result.extraction)
    result = await run_in_threadpool(repo.save, result) if repo else result
    return ReportReceipts(settings).sign_analysis(result)


@router.post("/jobs/match", response_model=JobMatchResponse, summary="Match pasted job text against a resume or a private stored analysis")
async def match_job(payload: JobMatchRequest, request: Request):
    repo = repository(request) if payload.analysis_id is not None else None
    if repo:
        parsed = await run_in_threadpool(repo.resume_for_match, payload.analysis_id)
    else:
        parsed = payload.resume.model_dump()
    try:
        result = await run_in_threadpool(MatchingService(request.app.state.settings.matching_weights).match,
                                        parsed, payload.job_description, payload.weights)
    except Exception:
        raise HTTPException(503, detail={"code": "matching_unavailable", "message": "Matching is temporarily unavailable."}) from None
    ident = await run_in_threadpool(repo.save_match, payload.analysis_id, payload.job_description, result) if payload.store else None
    response = JobMatchResponse(id=ident, analysis_id=payload.analysis_id, stored=payload.store, result=result)
    return ReportReceipts(request.app.state.settings).sign_match(response, parsed["text"], payload.job_description)


@router.get("/analyses", response_model=AnalysisPage, summary="List the configured owner's unexpired analysis summaries")
async def list_analyses(request: Request, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)):
    return await run_in_threadpool(repository(request).list, limit, offset)


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetail, summary="Read one unexpired owned analysis and its saved matches")
async def get_analysis(analysis_id: UUID, request: Request, match_limit: int = Query(20, ge=1, le=50),
                       match_offset: int = Query(0, ge=0, le=100000)):
    return await run_in_threadpool(repository(request).get, analysis_id, match_limit, match_offset)


@router.delete("/analyses/{analysis_id}", status_code=204, summary="Delete analysis, structured data, jobs and matches together")
async def delete_analysis(analysis_id: UUID, request: Request):
    await run_in_threadpool(repository(request).delete, analysis_id)
    return Response(status_code=204)
