"""FastAPI composition with secure deployment defaults and optional history."""
import asyncio
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse
from pydantic import SecretStr

from app.api.analyses import router as analyses_router
from app.api.extraction import router as extraction_router
from app.api.health import router as health_router
from app.api.matching import router as matching_router
from app.api.resumes import UploadBodyLimitMiddleware, router as resumes_router
from app.api.reports import router as reports_router
from app.core.config import Settings
from app.core.security import PrivacyAccessMiddleware, api_access
from app.db.repository import AnalysisRepository, HistoryLimitExceeded, HistoryNotFound
from app.db.retention import retention_worker
from app.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    # Private signing material is never the browser's bearer token. One worker
    # works without configuration; replicas need a shared server-only secret.
    if not settings.report_signing_key or not settings.report_signing_key.get_secret_value():
        settings.report_signing_key = SecretStr(secrets.token_urlsafe(48))

    @asynccontextmanager
    async def lifespan(application):
        if settings.deployment_environment == "production":
            import sys
            if not sys.platform.startswith("linux"):
                raise RuntimeError("Production isolated parsing requires Linux resource limits.")
        if settings.deployment_environment == "production" and settings.require_ner_model:
            from app.services.extraction.ner import load_model
            try:
                available = load_model(settings.spacy_model) is not None
            except Exception:
                available = False
            if not available:
                raise RuntimeError("Required NER model is unavailable; startup aborted.") from None
        database = None
        if settings.storage_enabled:
            try:
                database = Database(settings.database_url.get_secret_value())
            except Exception:
                raise RuntimeError("Database configuration is invalid; verify environment settings.") from None
        application.state.database = database
        stop = asyncio.Event()
        task = asyncio.create_task(retention_worker(AnalysisRepository(database, settings), stop,
                                    settings.retention_cleanup_interval_seconds)) if database else None
        try:
            yield
        finally:
            stop.set()
            if task:
                await task
            if database:
                database.dispose()

    application = FastAPI(title=settings.app_name, version="0.8.0", lifespan=lifespan,
        description="Anonymous stateless resume analysis, matching and signed snapshot reports. Stored history is inaccessible in anonymous mode. Legacy single-user mode retains owner authentication.")
    application.state.settings = settings
    application.state.database = None

    @application.exception_handler(RequestValidationError)
    async def private_validation_error(request, exc):
        errors = [{"loc": e["loc"], "type": e["type"], "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": {"code": "database_unavailable", "message": "Stored data is temporarily unavailable. No database details are exposed."}})

    @application.exception_handler(HistoryNotFound)
    async def not_found(request, exc):
        return JSONResponse(status_code=404, content={"detail": {"code": "analysis_not_found", "message": "Analysis not found or expired."}})

    @application.exception_handler(HistoryLimitExceeded)
    async def history_limit(request, exc):
        return JSONResponse(status_code=409, content={"detail": {"code": "history_limit", "message": "Saved history limit reached. Delete records before saving more."}})

    @application.exception_handler(Exception)
    async def private_unexpected_error(request, exc):
        return JSONResponse(status_code=500, content={"detail": {"code": "internal_error", "message": "The request could not be completed."}}, headers={"Cache-Control": "no-store"})

    application.add_middleware(UploadBodyLimitMiddleware, max_body_bytes=settings.max_upload_bytes + 64 * 1024)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    application.add_middleware(PrivacyAccessMiddleware, settings=settings)
    application.add_middleware(CORSMiddleware, allow_origins=[str(o).rstrip("/") for o in settings.cors_origins],
                               allow_credentials=False, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type", "Authorization"])
    application.include_router(health_router)
    for router in (resumes_router, extraction_router, matching_router, analyses_router, reports_router):
        application.include_router(router, dependencies=[] if settings.app_mode == "anonymous" else [Depends(api_access)])
    return application


app = create_app()
