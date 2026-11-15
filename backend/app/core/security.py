"""Single-principal authorization and early bounded request concurrency."""
import hashlib
import secrets
import logging
from threading import BoundedSemaphore

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import JSONResponse

bearer = HTTPBearer(auto_error=False, scheme_name="SingleUserBearer",
                    description="One deployment-owner token. Not multi-user login or a JWT. Never put it in VITE_ variables.")
LEGACY_PATHS = {"/api/v1/resumes/parse-text", "/api/v1/resumes/extract", "/api/v1/resumes/match"}


def access_error(settings, path, authorization):
    key = settings.single_user_api_key.get_secret_value() if settings.single_user_api_key else ""
    if settings.app_mode == "local" and not key and path.rstrip("/") in LEGACY_PATHS:
        return None
    if not key:
        return 503, "auth_not_configured", "Configure the single-user access token before using this API."
    parts = authorization.split() if authorization else []
    if len(parts) != 2 or parts[0].lower() != "bearer" or not secrets.compare_digest(
        hashlib.sha256(parts[1].encode()).digest(), hashlib.sha256(key.encode()).digest()
    ):
        return 401, "unauthorized", "A valid bearer token is required."
    return None


async def api_access(request: Request, credentials: HTTPAuthorizationCredentials | None = Security(bearer)):
    error = access_error(request.app.state.settings, request.url.path, request.headers.get("authorization"))
    if error:
        status, code, message = error
        raise HTTPException(status, detail={"code": code, "message": message}, headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)


class PrivacyAccessMiddleware:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.processing = BoundedSemaphore(settings.max_concurrent_processing)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/"):
            return await self.app(scope, receive, send)

        response_started = False

        async def private_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = list(message.get("headers", []))
                headers += [(b"cache-control", b"no-store"), (b"pragma", b"no-cache"), (b"x-content-type-options", b"nosniff")]
                message = {**message, "headers": headers}
            await send(message)

        auth_headers = [v.decode("latin-1") for k, v in scope.get("headers", []) if k.lower() == b"authorization"]
        error = access_error(self.settings, scope["path"], auth_headers[0] if len(auth_headers) == 1 else None)
        if error:
            status, code, message = error
            response = JSONResponse({"detail": {"code": code, "message": message}}, status_code=status,
                                    headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)
            return await response(scope, receive, private_send)
        acquired = False
        if scope["method"] == "POST":
            acquired = self.processing.acquire(blocking=False)
            if not acquired:
                response = JSONResponse({"detail": {"code": "processing_busy", "message": "Processing capacity is busy; retry later."}},
                                        status_code=429, headers={"Retry-After": "2"})
                return await response(scope, receive, private_send)
        try:
            await self.app(scope, receive, private_send)
        except Exception:
            logging.getLogger("app.security").error("api_request_failed")
            # Prevent outer server traceback logging of unforeseen errors whose
            # exception strings could contain resume text, SQL data or credentials.
            if not response_started:
                response = JSONResponse({"detail": {"code": "internal_error", "message": "The request could not be completed."}}, status_code=500)
                await response(scope, receive, private_send)
            else:
                await send({"type": "http.response.body", "body": b"", "more_body": False})
        finally:
            if acquired:
                self.processing.release()
