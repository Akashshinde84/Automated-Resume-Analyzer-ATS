"""Report integrity, ownership, content, rendering boundaries and legacy compatibility."""
from copy import deepcopy
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from pdfminer.high_level import extract_text
import pytest

from app.main import create_app
from app.services.reports import PDFReport
from app.services.report_receipts import ReportReceipts
from test_production_api import AUTH, analyze, client, counts, database_url, settings  # noqa: F401


def comparison(client, analysis, *, store=False, job="Required: Python, SQL. Preferred: Docker."):
    source = {"analysis_id": analysis["id"]} if analysis["id"] else {"resume": {"text": analysis["parsed"]["text"]}}
    response = client.post("/api/v1/jobs/match", json={**source, "job_description": job, "store": store})
    assert response.status_code == 200
    return response.json(), job


def test_stateless_json_pdf_full_flow(docx_bytes):
    from docx import Document
    document = Document(BytesIO(docx_bytes))
    document.paragraphs[0].insert_paragraph_before("Name: José 李明")
    stream = BytesIO()
    document.save(stream)
    docx_bytes = stream.getvalue()
    with TestClient(create_app(settings()), headers=AUTH) as client:
        data = analyze(client, docx_bytes, store=False).json()
        matched, job = comparison(client, data)
        payload = {"snapshot": data, "match": matched, "job_description": job, "format": "json"}
        response = client.post("/api/v1/reports", json=payload)
        assert response.status_code == 200
        report = response.json()
        assert report["analysis"]["extraction"]["candidate"] == data["extraction"]["candidate"]
        assert report["match"]["result"] == matched["result"]
        assert "report_token" not in response.text and "Bearer" not in response.text
        assert "José" in response.text and "李明" in response.text
        assert response.headers["content-disposition"] == 'attachment; filename="resume-analysis.json"'
        pdf = client.post("/api/v1/reports", json={**payload, "format": "pdf"})
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
        text = extract_text(BytesIO(pdf.content))
        for expected in ("Resume analysis report", "Job Match Score", "ATS readiness", "Python", "Missing required skills", "Evidence-based next steps", "PRIVATE", "Page 1", "Unicode codepoints"):
            assert expected in text
        assert "[U+674E]" in text and "[U+660E]" in text
        assert pdf.headers["content-type"] == "application/pdf"
        assert "no-store" in pdf.headers["cache-control"]


@pytest.mark.parametrize("tamper", ["candidate", "skill", "score", "job", "resume", "token"])
def test_rejects_forged_snapshots(client, docx_bytes, tamper):
    data = analyze(client, docx_bytes, store=False).json()
    matched, job = comparison(client, data)
    payload = {"snapshot": data, "match": matched, "job_description": job, "format": "json"}
    if tamper == "candidate":
        payload["snapshot"]["extraction"]["candidate"]["name"] = "Invented Candidate"
    elif tamper == "skill":
        payload["snapshot"]["parsed"]["skills"][0]["name"] = "Invented Skill"
    elif tamper == "score":
        payload["match"]["result"]["scores"]["overall"] = 99.9
    elif tamper == "job":
        payload["job_description"] = "Different job"
    elif tamper == "resume":
        payload["snapshot"]["parsed"]["text"] += "Extra qualification"
    else:
        payload["snapshot"]["report_token"] = "malformed"
    response = client.post("/api/v1/reports", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_report_snapshot"


def test_saved_report_scope_deletion_and_no_unrelated_matches(client, docx_bytes):
    first = analyze(client, docx_bytes).json()
    second = analyze(client, docx_bytes).json()
    selected, job = comparison(client, first, store=True)
    other, _ = comparison(client, first, store=True, job="Required: Kubernetes")
    payload = {"analysis_id": first["id"], "match_id": selected["id"], "format": "json"}
    report = client.post("/api/v1/reports", json=payload).json()
    assert report["analysis"]["id"] == first["id"] and report["match"]["id"] == selected["id"]
    assert report["match"]["job_description"] == job
    assert other["id"] not in str(report) and "matches" not in report["analysis"]
    assert counts(client) == [2, 2, 2, 2]
    assert client.post("/api/v1/reports", json={**payload, "analysis_id": second["id"]}).status_code == 404
    assert client.post("/api/v1/reports", json=payload, headers={"Authorization": "Bearer wrong"}).status_code == 401
    original = client.app.state.settings.single_user_id
    client.app.state.settings.single_user_id = "other-owner"
    assert client.post("/api/v1/reports", json=payload).status_code == 404
    client.app.state.settings.single_user_id = original
    client.delete("/api/v1/analyses/" + first["id"])
    assert client.post("/api/v1/reports", json=payload).status_code == 404
    assert client.post("/api/v1/reports", json={"snapshot": first, "format": "json"}).status_code == 422


def test_signed_match_cannot_be_reused_for_another_resume(client, docx_bytes):
    first = analyze(client, docx_bytes).json()
    second = analyze(client, docx_bytes).json()
    matched, job = comparison(client, first)
    assert client.post("/api/v1/reports", json={"analysis_id": second["id"], "match": matched, "job_description": job, "format": "json"}).status_code == 409


def test_bearer_key_alone_cannot_forge_receipts_and_reports_require_auth(client, docx_bytes):
    from app.schemas.analysis import AnalysisResponse
    data = analyze(client, docx_bytes, store=False).json()
    attacker = ReportReceipts(settings(report_signing_key="different-server-secret-" + "x" * 40))
    forged = attacker.sign_analysis(AnalysisResponse.model_validate(data)).model_dump(mode="json")
    assert client.post("/api/v1/reports", json={"snapshot": forged, "format": "json"}).status_code == 409
    assert client.post("/api/v1/reports", json={"snapshot": data, "format": "pdf"}, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_receipt_expiry_owner_and_key_rotation(client, docx_bytes, monkeypatch):
    data = analyze(client, docx_bytes, store=False).json()
    payload = {"snapshot": data, "format": "json"}
    from app.services import report_receipts
    actual = report_receipts.time.time()
    monkeypatch.setattr(report_receipts.time, "time", lambda: actual + 7200)
    assert client.post("/api/v1/reports", json=payload).status_code == 409
    monkeypatch.setattr(report_receipts.time, "time", lambda: actual)
    client.app.state.settings.single_user_id = "another-owner"
    assert client.post("/api/v1/reports", json=payload).status_code == 409
    receipts = ReportReceipts(settings(single_user_id="primary", report_signing_key="server-only-" + "x" * 40))
    receipts.key = b"rotated"
    from app.schemas.analysis import AnalysisResponse
    from app.services.report_receipts import InvalidReportSnapshot
    with pytest.raises(InvalidReportSnapshot):
        receipts.verify_analysis(AnalysisResponse.model_validate(data))


@pytest.mark.parametrize("extra", [{"format": "html"}, {"match_id": str(uuid4())}, {"job_description": "unbound job"}, {"unexpected": "value"}])
def test_invalid_report_requests(client, docx_bytes, extra):
    data = analyze(client, docx_bytes, store=False).json()
    assert client.post("/api/v1/reports", json={"snapshot": data, "format": "json", **extra}).status_code == 422


def test_analysis_only_empty_pdf_and_safe_failure(client, make_pdf, monkeypatch):
    data = client.post("/api/v1/resumes/analyze", files={"file": ("scan.pdf", make_pdf(image=True))}).json()
    payload = {"snapshot": data, "format": "json"}
    result = client.post("/api/v1/reports", json=payload).json()
    assert result["match"] is None and result["analysis"]["parsed"]["warnings"]
    pdf = client.post("/api/v1/reports", json={**payload, "format": "pdf"})
    assert "Job Match Score is unavailable" in extract_text(BytesIO(pdf.content))
    def failure(*args):
        raise RuntimeError("Sensitive internal content should not be exposed")
    monkeypatch.setattr(PDFReport, "render", failure)
    response = client.post("/api/v1/reports", json={**payload, "format": "pdf"})
    assert response.status_code == 503 and "Sensitive" not in response.text


def test_report_budget_markup_long_text_and_schema(client, docx_bytes):
    data = analyze(client, docx_bytes, store=False).json()
    from app.schemas.analysis import AnalysisResponse
    from app.schemas.reports import AnalysisReport
    from datetime import datetime, timezone
    # Service-level synthetic stress case; no forged endpoint snapshot accepted.
    modified = deepcopy(data)
    modified["parsed"]["sections"]["summary"] = '<img src="https://example.invalid/private"/>' + "A" * 65000
    report = AnalysisReport(generated_at=datetime.now(timezone.utc), analysis=AnalysisResponse.model_validate(modified))
    pdf = PDFReport().render(report)
    text = extract_text(BytesIO(pdf))
    assert "presentation budget" in text and "<img" in text
    schema = client.get("/openapi.json").json()
    response = schema["paths"]["/api/v1/reports"]["post"]["responses"]["200"]["content"]
    assert response["application/json"]["schema"]["$ref"] == "#/components/schemas/AnalysisReport"
    assert "application/pdf" in response
    oversized = client.post("/api/v1/reports", content=b"x" * 4_194_305, headers={"Content-Type": "application/json"})
    assert oversized.status_code == 413
