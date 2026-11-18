"""Anonymous allowlist, bounded rate/concurrency limits and legacy owner access."""
import hashlib
import secrets
import logging
from threading import BoundedSemaphore
from threading import Lock
from collections import deque
import time

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import JSONResponse

bearer = HTTPBearer(auto_error=False, scheme_name="SingleUserBearer",
                    description="One deployment-owner token. Not multi-user login or a JWT. Never put it in VITE_ variables.")
LEGACY_PATHS = {"/api/v1/resumes/parse-text", "/api/v1/resumes/extract", "/api/v1/resumes/match"}
PUBLIC_PATHS = LEGACY_PATHS | {"/api/v1/resumes/analyze", "/api/v1/jobs/match", "/api/v1/reports"}


def access_error(settings, path, authorization):
    if settings.app_mode == "anonymous":
        if path.rstrip("/") in PUBLIC_PATHS:
            return None
        return 403, "private_history_disabled", "Stored analyses and administrative operations are unavailable in anonymous mode."
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
        self.rate_lock = Lock()
        self.rate_salt = secrets.token_bytes(32)
        self.rate_clients = {}
        self.rate_global = deque()

    def rate_allowed(self, scope):
        now = time.monotonic()
        host = (scope.get("client") or ("unknown",))[0]
        # Never retain raw IP addresses or trust client-supplied forwarding headers.
        client = hashlib.sha256(self.rate_salt + host.encode()).digest()
        with self.rate_lock:
            self.rate_clients = {k: v for k, v in self.rate_clients.items() if v and v[-1] > now - 60}
            for queue in (self.rate_global, self.rate_clients.get(client, deque())):
                while queue and queue[0] <= now - 60:
                    queue.popleft()
            if client not in self.rate_clients and len(self.rate_clients) >= 4096:
                return False
            queue = self.rate_clients.setdefault(client, deque())
            if len(queue) >= self.settings.anonymous_requests_per_minute or len(self.rate_global) >= self.settings.anonymous_global_requests_per_minute:
                return False
            queue.append(now)
            self.rate_global.append(now)
            return True

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
            if self.settings.app_mode == "anonymous" and not self.rate_allowed(scope):
                response = JSONResponse({"detail": {"code": "rate_limited", "message": "Too many processing requests. Please wait a minute and retry."}},
                                        status_code=429, headers={"Retry-After": "60"})
                return await response(scope, receive, private_send)
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
