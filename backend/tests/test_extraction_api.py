from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app
from app.schemas.candidate import ExtractionResult
from app.services.extraction import InformationExtractor
from app.services.extraction.ner import SpacyNER

URL = "/api/v1/resumes/extract"


@pytest.fixture
def client():
    with TestClient(create_app(Settings(_env_file=None, spacy_model="not_installed_test_model"))) as connection:
        yield connection


def test_typed_api_and_missing_model(client):
    response = client.post(URL, json={"text": "Name: Jane Example\njane@example.test\nPhone: 020 7946 0018", "phone_region": "gb"})
    assert response.status_code == 200
    result = ExtractionResult.model_validate(response.json())
    assert result.candidate.name == "Jane Example"
    assert result.candidate.phones[0].e164 == "+442079460018"
    assert result.nlp.status == "unavailable"
    assert any("model unavailable" in w for w in result.warnings)


def test_no_default_country(client):
    response = client.post(URL, json={"text": "Phone: 98765 43210"})
    assert response.status_code == 200
    assert response.json()["candidate"]["phones"][0]["e164"] is None


@pytest.mark.parametrize("payload", [
    {}, {"text": ["private"]}, {"text": "sensitive", "phone_region": "XX"},
    {"text": "sensitive", "unexpected": "private"}, {"text": "PRIVATE" * 17000},
])
def test_invalid_input_does_not_echo_resume(client, payload, caplog):
    response = client.post(URL, json=payload)
    assert response.status_code == 422
    assert "sensitive" not in response.text
    assert "PRIVATE" not in response.text
    assert '"input"' not in response.text
    assert "sensitive" not in caplog.text
    assert "PRIVATE" not in caplog.text


def test_extractor_failure_is_private(client, monkeypatch, caplog):
    def fail(*args):
        raise RuntimeError("PRIVATE jordan@example.test")
    monkeypatch.setattr(InformationExtractor, "extract", fail)
    response = client.post(URL, json={"text": "PRIVATE jordan@example.test"})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["code"] == "extraction_failed"
    assert detail["diagnostic_id"] in caplog.text
    assert "stage=candidate_extraction exception_type=RuntimeError" in caplog.text
    assert "PRIVATE" not in response.text + caplog.text
    assert "jordan@example.test" not in response.text + caplog.text


def test_json_body_limit(client):
    response = client.post(URL, content=iter([b"x" * 400000, b"y" * 400000]), headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_parse_text_to_candidate_pipeline(client, docx_bytes):
    parsed = client.post("/api/v1/resumes/parse-text", files={"file": ("synthetic.docx", docx_bytes)})
    assert parsed.status_code == 200
    response = client.post(URL, json={"text": parsed.json()["text"]})
    assert response.status_code == 200
    result = response.json()["candidate"]
    assert result["emails"] == ["jose@example.test"]
    assert result["education"][0]["institution"] == "Université de Montréal"
    assert result["education"][0]["degree"] is None


def test_sensitive_content_is_not_logged(client, caplog):
    secret = "SYNTHETIC_PRIVATE_MARKER"
    response = client.post(URL, json={"text": f"Name: Jane Example\njane@example.test\nSummary\n{secret}"})
    assert response.status_code == 200
    assert secret not in caplog.text
    assert "jane@example.test" not in caplog.text


def test_openapi_exposes_nested_schema(client):
    schema = client.get("/openapi.json").json()
    response = schema["paths"][URL]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response["$ref"].endswith("/ExtractionResult")
    assert "Education" in schema["components"]["schemas"]
