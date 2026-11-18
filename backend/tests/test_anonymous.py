"""Anonymous processing never grants access to private stored records."""
from copy import deepcopy
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.core.config import Settings
from app.main import create_app
from test_production_api import client, database_url, counts, analyze, AUTH  # noqa: F401


def anonymous(**kwargs):
    return Settings(_env_file=None, app_mode="anonymous", **kwargs)


def test_public_analyze_match_reports_and_tamper_protection(docx_bytes):
    with TestClient(create_app(anonymous())) as connection:
        response = connection.post("/api/v1/resumes/analyze", files={"file": ("resume.docx", docx_bytes)})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] is None and not data["stored"]
        assert connection.app.state.database is None
        job = "Required skills: Python, SQL. Preferred skills: Docker."
        response = connection.post("/api/v1/jobs/match", json={"resume": {"text": data["parsed"]["text"]}, "job_description": job})
        assert response.status_code == 200
        match = response.json()
        payload = {"snapshot": data, "match": match, "job_description": job}
        for kind in ("json", "pdf"):
            response = connection.post("/api/v1/reports", json={**payload, "format": kind})
            assert response.status_code == 200
            assert "no-store" in response.headers["cache-control"]
            if kind == "pdf":
                assert response.content.startswith(b"%PDF-")
        forged = deepcopy(payload)
        forged["snapshot"]["extraction"]["candidate"]["name"] = "Fabricated"
        assert connection.post("/api/v1/reports", json={**forged, "format": "json"}).status_code == 409
        unrelated = connection.post("/api/v1/resumes/analyze", files={"file": ("other.pdf", b"bad")})
        assert unrelated.status_code == 415


def test_existing_private_history_is_inaccessible_even_with_owner_header(client, docx_bytes):
    saved = analyze(client, docx_bytes).json()
    before = counts(client)
    # Sharing a DB URL here cannot enable anonymous database access.
    with TestClient(create_app(anonymous(database_url=client.app.state.settings.database_url))) as public:
        for headers in ({}, AUTH):
            for method, path in [("GET", "/api/v1/analyses"), ("GET", f'/api/v1/analyses/{saved["id"]}'),
                                 ("DELETE", f'/api/v1/analyses/{saved["id"]}')]:
                assert public.request(method, path, headers=headers).status_code == 403
            assert public.post("/api/v1/resumes/analyze?store=true", headers=headers,
                               files={"file": ("resume.docx", docx_bytes)}).status_code == 403
            assert public.post("/api/v1/jobs/match", headers=headers,
                               json={"analysis_id": saved["id"], "job_description": "Required: Python"}).status_code == 403
            assert public.post("/api/v1/reports", headers=headers,
                               json={"analysis_id": saved["id"], "format": "json"}).status_code == 403
        assert public.app.state.database is None
    assert counts(client) == before


def test_anonymous_rejects_persistence_configuration():
    with pytest.raises(ValidationError):
        anonymous(storage_enabled=True, single_user_api_key="x" * 48, database_url="sqlite:///:memory:")


def test_production_anonymous_configuration_requires_no_owner_token():
    settings = anonymous(deployment_environment="production", report_signing_key="s" * 48,
                         require_ner_model=True, isolate_parsing=True,
                         cors_origins=["https://frontend.example.test"])
    assert settings.single_user_api_key is None
    assert "securitySchemes" not in create_app(settings).openapi().get("components", {})


@pytest.mark.parametrize("setting", ["anonymous_requests_per_minute", "anonymous_global_requests_per_minute"])
def test_public_rate_limit_includes_invalid_requests_and_cannot_spoof_forwarding(setting):
    with TestClient(create_app(anonymous(**{setting: 2}))) as connection:
        for i in range(2):
            assert connection.post("/api/v1/resumes/parse-text", headers={"X-Forwarded-For": str(uuid4())},
                files={"file": ("resume.pdf", b"invalid")}).status_code == 415
        response = connection.post("/api/v1/resumes/parse-text", files={"file": ("resume.pdf", b"invalid")})
        assert response.status_code == 429
        assert response.json()["detail"]["code"] == "rate_limited"
        assert response.headers["retry-after"] == "60"
        assert connection.get("/health").status_code == 200


def test_public_legacy_endpoints_and_invalid_inputs(make_pdf):
    with TestClient(create_app(anonymous())) as connection:
        assert connection.post("/api/v1/resumes/parse-text", files={"file": ("resume.pdf", make_pdf(["Skills", "Python"]))}).status_code == 200
        assert connection.post("/api/v1/resumes/extract", json={"text": "Name: Alex Example\nSkills: Python"}).status_code == 200
        assert connection.post("/api/v1/resumes/match", json={"resume": {"text": "Skills: Python"}, "job_description": "Required: Python"}).status_code == 200
        assert connection.post("/api/v1/jobs/match", json={"resume": {"text": "Skills: Python"}, "job_description": " "}).status_code == 422
