"""Typed text-to-candidate endpoint. Bodies and exceptions are never logged."""
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.schemas.candidate import ExtractionRequest, ExtractionResult
from app.services.extraction import InformationExtractor
from app.services.extraction.ner import SpacyNER

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


def get_extractor(request: Request):
    return InformationExtractor(SpacyNER(request.app.state.settings.spacy_model))


@router.post("/extract", response_model=ExtractionResult)
async def extract_candidate(payload: ExtractionRequest, request: Request) -> ExtractionResult:
    extractor = get_extractor(request)
    try:
        return await run_in_threadpool(extractor.extract, payload.text, payload.phone_region)
    except Exception:
        # Avoid exception interpolation/tracebacks that could expose resume text.
        raise HTTPException(503, detail={"code": "extraction_unavailable", "message": "Candidate extraction is temporarily unavailable."}) from None
