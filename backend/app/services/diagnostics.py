"""Content-free diagnostics for failures outside the isolated decoder."""
import logging
import re
from uuid import uuid4


def failure_reference(stage, exc):
    reference = uuid4().hex[:12]
    name = type(exc).__name__
    safe_name = name if re.fullmatch(r"[A-Za-z_]{1,64}", name) else "Exception"
    # Never interpolate the exception, request, traceback, filename or resume.
    logging.getLogger("app.processing").error(
        "processing_failure reference=%s stage=%s exception_type=%s",
        reference, stage, safe_name,
    )
    return reference
