"""Internal decoder entry point. No request data or exceptions are logged."""
import json
from pathlib import Path
import sys


def main():
    source, destination, upload, expansion, pages, memory, seconds, strict = sys.argv[1:]
    try:
        import resource
    except ImportError:
        if strict == "1":
            return 2  # Production requires Linux resource limits; never silently downgrade.
    else:
        resource.setrlimit(resource.RLIMIT_AS, (int(memory) * 1024**2,) * 2)
        resource.setrlimit(resource.RLIMIT_CPU, (max(1, int(seconds) - 1), int(seconds)))
        resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024**2,) * 2)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # -I excludes the working directory and PYTHONPATH. Add only our trusted code.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.services.parser import ResumeParser, ResumeParseError
    try:
        result = ResumeParser(int(upload), int(expansion), int(pages)).parsefile(source)
        if len(result["text"]) > 100_000:
            raise ResumeParseError("extracted_text_limit", "Extracted text exceeds the analysis limit.", 413)
        envelope = {"result": result}
    except ResumeParseError as exc:
        envelope = {"error": {"code": exc.code, "message": str(exc), "status": exc.status_code}}
    except Exception:
        return 3
    Path(destination).write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
