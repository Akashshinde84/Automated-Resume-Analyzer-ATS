"""Request and file bounds for the local resume upload endpoint."""
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.responses import JSONResponse

from app.services.parser import ResumeParseError, ResumeParser

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])
UPLOAD_PATH = "/api/v1/resumes/parse-text"


class UploadBodyLimitMiddleware:
    """Bound the entire multipart body before the framework parses/spools it.

    A bounded in-memory buffer also covers chunked requests without Content-Length.
    File bytes have their own stricter limit; 64 KiB is reserved for form overhead.
    """
    def __init__(self, app, max_body_bytes: int):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"].rstrip("/") not in {UPLOAD_PATH, "/api/v1/resumes/analyze", "/api/v1/resumes/extract", "/api/v1/resumes/match", "/api/v1/jobs/match", "/api/v1/reports"}:
            return await self.app(scope, receive, send)
        limit = 601_024 if scope["path"].rstrip("/").endswith("/extract") else self.max_body_bytes
        if scope["path"].rstrip("/").endswith("/match"):
            limit = 2_097_152
        if scope["path"].rstrip("/").endswith("/reports"):
            limit = 4_194_304
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > limit:
                response = JSONResponse(status_code=413, content={"detail": {
                    "code": "request_too_large", "message": "The request exceeds the configured size limit."
                }})
                return await response(scope, receive, send)
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        consumed = False

        async def bounded_receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


def _parse_upload(upload: UploadFile, filename: str, parser: ResumeParser, settings=None) -> dict:
    # Never use the client filename as a local path; Windows requires closing the
    # writable handle before reopening it in the parser. Context cleanup covers errors.
    with TemporaryDirectory(prefix="resume-") as directory:
        path = Path(directory) / ("resume" + Path(filename).suffix.lower())
        upload.file.seek(0)
        with path.open("wb") as target:
            size = 0
            while chunk := upload.file.read(64 * 1024):
                size += len(chunk)
                if size > parser.max_size_bytes:
                    raise ResumeParseError("file_too_large", "The file exceeds the configured upload limit.", 413)
                target.write(chunk)
        if settings and settings.isolate_parsing:
            from app.services.isolated_parser import parse_isolated
            result = parse_isolated(path, parser, settings)
        else:
            result = parser.parsefile(path)
        result["metadata"]["filename"] = filename
        return result


async def read_resume_upload(request: Request, allow_phone_region: bool = False):
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "multipart/form-data":
        raise HTTPException(415, detail={"code": "invalid_content_type", "message": "Send multipart/form-data with one file field."})
    async with request.form(max_files=1, max_fields=1 if allow_phone_region else 0, max_part_size=64 * 1024) as form:
        upload = form.get("file")
        allowed = {"file", "phone_region"} if allow_phone_region else {"file"}
        if (not isinstance(upload, UploadFile) or any(key not in allowed for key in form)
                or len(form.multi_items()) != len(form)):
            raise HTTPException(422, detail={"code": "missing_file", "message": "Exactly one file field named 'file' is required."})
        filename = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        filename = "".join(c for c in filename if c.isprintable())[:255]
        if Path(filename).suffix.lower() not in {".pdf", ".docx"}:
            raise HTTPException(415, detail={"code": "unsupported_type", "message": "Only PDF and DOCX files are supported."})
        settings = request.app.state.settings
        parser = ResumeParser(settings.max_upload_bytes, settings.max_docx_uncompressed_bytes, settings.max_pdf_pages)
        try:
            parsed = await run_in_threadpool(_parse_upload, upload, filename, parser, settings)
            return parsed, form.get("phone_region") if allow_phone_region else None
        except ResumeParseError as exc:
            detail = {"code": exc.code, "message": str(exc)}
            if getattr(exc, "diagnostic_id", None):
                detail["diagnostic_id"] = exc.diagnostic_id
            raise HTTPException(exc.status_code, detail=detail) from None


@router.post("/parse-text")
async def parse_text(request: Request) -> dict:
    parsed, _ = await read_resume_upload(request)
    return parsed
