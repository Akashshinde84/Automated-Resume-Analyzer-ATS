"""Local, typed matching endpoint with sanitized errors and no body logging."""
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.schemas.matching import MatchingRequest, MatchingResponse
from app.services.matching import MatchingService

router = APIRouter(prefix="/api/v1/resumes", tags=["matching"])


@router.post("/match", response_model=MatchingResponse)
async def match_resume(payload: MatchingRequest, request: Request) -> MatchingResponse:
    service = MatchingService(weights=request.app.state.settings.matching_weights)
    try:
        return await run_in_threadpool(service.match, payload.resume.model_dump(), payload.job_description, payload.weights)
    except Exception:
        raise HTTPException(503, detail={"code": "matching_unavailable", "message": "Matching is temporarily unavailable."}) from None
