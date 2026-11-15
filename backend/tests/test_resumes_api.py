from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app
from app.services.parser import ResumeParser

URL = "/api/v1/resumes/parse-text"


@pytest.fixture
def client():
    with TestClient(create_app(Settings(_env_file=None))) as connection:
        yield connection


@pytest.mark.parametrize("file_type", ["pdf", "docx"])
def test_upload_success(client, make_pdf, docx_bytes, file_type):
    content = make_pdf(["Skills", "Python"]) if file_type == "pdf" else docx_bytes
    response = client.post(URL, files={"file": (f"resume.{file_type}", content, "application/octet-stream")})
    assert response.status_code == 200
    result = response.json()
    assert "Python" in result["sections"]["skills"]
    assert result["metadata"]["filename"] == f"resume.{file_type}"
    assert result["metadata"]["size_bytes"] == len(content)
    assert isinstance(result["warnings"], list)


@pytest.mark.parametrize("filename, content, status, code", [
    ("r.exe", b"abc", 415, "unsupported_type"),
    ("r.pdf", b"wrong signature", 415, "invalid_signature"),
    ("r.pdf", b"", 422, "empty_file"),
    ("r.pdf", b"%PDF-1.7\nbroken", 422, "corrupt_file"),
])
def test_upload_errors(client, filename, content, status, code):
    response = client.post(URL, files={"file": (filename, content)})
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_upload_encrypted(client, make_pdf):
    response = client.post(URL, files={"file": ("encrypted.pdf", make_pdf(["Secret"], encrypted=True))})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "encrypted_pdf"


def test_upload_scan_returns_warning(client, make_pdf):
    response = client.post(URL, files={"file": ("scan.pdf", make_pdf(image=True))})
    assert response.status_code == 200
    assert response.json()["text"] == ""
    assert any("OCR" in warning for warning in response.json()["warnings"])


def test_upload_file_size_limit(make_pdf):
    with TestClient(create_app(Settings(_env_file=None, max_upload_bytes=100))) as client:
        response = client.post(URL, files={"file": ("r.pdf", make_pdf(["Hello"]))})
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"


def test_request_limit_without_content_length():
    with TestClient(create_app(Settings(_env_file=None, max_upload_bytes=100))) as client:
        response = client.post(URL, content=iter([b"a" * 40000, b"b" * 40000]), headers={"Content-Type": "multipart/form-data; boundary=test"})
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_too_large"


def test_multipart_requires_one_file(client, make_pdf):
    content = make_pdf(["Hello"])
    response = client.post(URL, files=[("file", ("a.pdf", content)), ("file", ("b.pdf", content))])
    assert response.status_code == 400
    response = client.post(URL, files={"other": ("a.pdf", content)})
    assert response.status_code == 422


def test_wrong_content_type_and_bad_multipart(client):
    assert client.post(URL, json={"file": "fake"}).status_code == 415
    response = client.post(URL, content=b"broken", headers={"Content-Type": "multipart/form-data"})
    assert response.status_code == 400


@pytest.mark.parametrize("valid", [False, True])
def test_temporary_file_cleanup_and_safe_filename(client, make_pdf, monkeypatch, valid):
    paths = []
    original = ResumeParser.parsefile

    def record(self, path):
        paths.append(Path(path))
        assert Path(path).name == "resume.pdf"
        return original(self, path)

    monkeypatch.setattr(ResumeParser, "parsefile", record)
    content = make_pdf(["Hello"]) if valid else b"%PDF-broken"
    response = client.post(URL, files={"file": ("../../private/resume.pdf", content)})
    assert response.status_code == (200 if valid else 422)
    assert paths
    assert all(not path.exists() and not path.parent.exists() for path in paths)
    if valid:
        assert response.json()["metadata"]["filename"] == "resume.pdf"


def test_cors_post(client):
    response = client.options(URL, headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
