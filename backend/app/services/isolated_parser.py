"""Run document decoders outside the API process with a hard wall-clock deadline."""
import json
import os
from pathlib import Path
import subprocess
import sys

from app.services.parser import ResumeParseError

MAX_RESULT_BYTES = 8 * 1024 * 1024


def parse_isolated(path, parser, settings):
    result_path = Path(path).with_suffix(".result.json")
    # The child does not need API/database/report secrets or network credentials.
    environment = {k: v for k, v in os.environ.items()
                   if k.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG"}}
    environment.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    command = [sys.executable, "-I", str(Path(__file__).with_name("parse_worker.py")),
               str(path), str(result_path), str(parser.max_size_bytes),
               str(parser.max_docx_uncompressed_bytes), str(parser.max_pdf_pages),
               str(settings.parser_memory_mb), str(settings.parser_timeout_seconds),
               "1" if settings.deployment_environment == "production" else "0"]
    try:
        completed = subprocess.run(command, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   timeout=settings.parser_timeout_seconds, check=False)
        if completed.returncode or not result_path.exists() or result_path.stat().st_size > MAX_RESULT_BYTES:
            raise ResumeParseError("parsing_resource_limit", "Document processing exceeded a resource limit or failed safely.")
        envelope = json.loads(result_path.read_text(encoding="utf-8"))
        if "error" in envelope:
            error = envelope["error"]
            raise ResumeParseError(error["code"], error["message"], error["status"])
        return envelope["result"]
    except subprocess.TimeoutExpired:
        # subprocess.run kills and waits for this decoder process before returning.
        raise ResumeParseError("parsing_timeout", "Document processing exceeded its time limit. Try a simpler text-based resume.") from None
    except ResumeParseError:
        raise
    except (OSError, ValueError, KeyError):
        raise ResumeParseError("parsing_failed", "The document could not be processed safely.") from None
    finally:
        result_path.unlink(missing_ok=True)
