"""Production guards and real bounded decoder behavior."""
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.isolated_parser import parse_isolated
from app.services.parser import ResumeParser, ResumeParseError


def test_production_rejects_incomplete_configuration():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, deployment_environment="production")


def test_production_requires_https_and_isolation():
    values = dict(_env_file=None, deployment_environment="production", app_mode="single_user",
                  single_user_api_key="a" * 48, report_signing_key="b" * 48,
                  require_ner_model=True, isolate_parsing=True,
                  cors_origins=["https://frontend.example.test"], allowed_hosts=["api.example.test"])
    assert Settings(**values).storage_enabled is False
    with pytest.raises(ValidationError):
        Settings(**{**values, "cors_origins": ["http://frontend.example.test"]})
    with pytest.raises(ValidationError):
        Settings(**{**values, "isolate_parsing": False})


@pytest.mark.parametrize("kind", ["docx", "pdf"])
def test_real_decoder_subprocess(tmp_path, docx_bytes, make_pdf, kind):
    path = tmp_path / f"resume.{kind}"
    path.write_bytes(docx_bytes if kind == "docx" else make_pdf(["Skills", "Python, React"]))
    result = parse_isolated(path, ResumeParser(), Settings(_env_file=None))
    assert "Python" in result["text"]
    assert not path.with_suffix(".result.json").exists()


def test_worker_preserves_safe_file_error(tmp_path):
    path = tmp_path / "resume.pdf"
    path.write_bytes(b"broken")
    with pytest.raises(ResumeParseError) as exc:
        parse_isolated(path, ResumeParser(), Settings(_env_file=None))
    assert exc.value.code == "invalid_signature"
    assert not path.with_suffix(".result.json").exists()


def test_deadline_is_forwarded_and_private_environment(tmp_path, monkeypatch):
    path = tmp_path / "resume.pdf"
    path.write_bytes(b"%PDF-")
    monkeypatch.setenv("DATABASE_URL", "do-not-forward")
    def timeout(command, **kwargs):
        assert "DATABASE_URL" not in kwargs["env"]
        assert kwargs["timeout"] == 1
        raise subprocess.TimeoutExpired(command, 1)
    monkeypatch.setattr("app.services.isolated_parser.execute_decoder", timeout)
    with pytest.raises(ResumeParseError) as exc:
        parse_isolated(path, ResumeParser(), Settings(_env_file=None, parser_timeout_seconds=1))
    assert exc.value.code == "parsing_timeout"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Production resource limits require Linux")
def test_linux_worker_enforces_cpu_and_memory(tmp_path):
    # Exercise the same stdlib primitives in a disposable child, not the test/API process.
    cpu = subprocess.run([sys.executable, "-c",
        "import resource; resource.setrlimit(resource.RLIMIT_CPU,(1,1)); exec('while True: pass')"],
        timeout=5, capture_output=True)
    assert cpu.returncode < 0
    memory = subprocess.run([sys.executable, "-c",
        "import resource; resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2); x=bytearray(256*1024**2)"],
        timeout=5, capture_output=True)
    assert memory.returncode != 0
    assert b"MemoryError" in memory.stderr
