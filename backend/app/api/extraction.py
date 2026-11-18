"""Typed text-to-candidate endpoint. Bodies and exceptions are never logged."""
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.schemas.candidate import ExtractionRequest, ExtractionResult
from app.services.extraction import InformationExtractor
from app.services.extraction.ner import SpacyNER
from app.services.diagnostics import failure_reference

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


def get_extractor(request: Request):
    return InformationExtractor(SpacyNER(request.app.state.settings.spacy_model))


@router.post("/extract", response_model=ExtractionResult)
async def extract_candidate(payload: ExtractionRequest, request: Request) -> ExtractionResult:
    extractor = get_extractor(request)
    try:
        return await run_in_threadpool(extractor.extract, payload.text, payload.phone_region,
                                       payload.hyperlinks, payload.layout_blocks)
    except Exception as exc:
        # Avoid exception interpolation/tracebacks that could expose resume text.
        reference = failure_reference("candidate_extraction", exc)
        raise HTTPException(500, detail={"code": "extraction_failed", "message": "Candidate analysis failed unexpectedly. Retry Analysis or contact the operator.", "diagnostic_id": reference}) from None
