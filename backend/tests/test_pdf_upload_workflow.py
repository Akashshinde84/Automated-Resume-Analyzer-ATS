"""End-to-end anonymous PDF regression with real decoding and report receipts."""
from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app
from app.services.sections import HEADINGS
from app.services.skills import get_skill_extractor


@pytest.mark.parametrize("section", list(HEADINGS))
def test_skill_evidence_accepts_every_recognized_section(section):
    text = HEADINGS[section][0] + "\nPython workshop"
    skills = get_skill_extractor().extract(text)
    python = next(skill for skill in skills if skill.name == "Python")
    assert python.occurrences[0].section == section
    assert text[python.occurrences[0].start:python.occurrences[0].end] == "Python"


@pytest.mark.parametrize("heading, section", [
    ("Extra Curricular Activities", "activities"), ("Interests", "other"),
])
def test_isolated_pdf_skill_in_new_section_does_not_crash(make_pdf, heading, section):
    content = make_pdf(["Name: Alex Example", heading, "Python workshop"])
    with TestClient(create_app(Settings(_env_file=None, app_mode="anonymous", isolate_parsing=True))) as client:
        response = client.post("/api/v1/resumes/analyze", files={"file": ("synthetic.pdf", content)})
        assert response.status_code == 200, response.text
        data = response.json()
        occurrence = data["parsed"]["skills"][0]["occurrences"][0]
        assert occurrence["section"] == section
        assert occurrence["source_type"] == "other"
        assert data["parsed"]["skills"][0]["explicitly_listed"] is False


def test_pdf_all_sections_and_reports_without_credentials(make_pdf):
    content = make_pdf([
        "Name: Alex Example", "alex@example.test", "Skills", "Python, React.js",
        "Education", "Example Institute of Technology", "B.Tech in Computer Science",
        "2021 - 2025", "Projects", "Project: Document Tool",
        "- Developed a resume parser using Python and React.js.",
        "- Integrated document uploads.", "Certifications",
        "Industrial Automation Certificate", "Siemens", "Jul 2024",
        "Extra Curricular Activities", "- Organized a university sports event.",
    ])
    settings = Settings(_env_file=None, app_mode="anonymous", isolate_parsing=True)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/resumes/analyze",
                               files={"file": ("synthetic.pdf", content)})
        assert response.status_code == 200, response.text
        data = response.json()
        candidate = data["extraction"]["candidate"]
        assert candidate["name"] == "Alex Example"
        assert candidate["emails"] == ["alex@example.test"]
        assert candidate["education"][0]["institution"] == "Example Institute of Technology"
        assert {s["name"] for s in data["parsed"]["skills"]} >= {"Python", "React"}
        assert len(candidate["projects"]) == 1
        assert candidate["projects"][0]["name"] == "Document Tool"
        assert "Integrated document uploads" in candidate["projects"][0]["description"]
        assert candidate["projects"][0]["urls"] == []
        assert candidate["certifications"][0]["issuer"] == "Siemens"
        assert candidate["activities"]
        assert data["stored"] is False
        for kind in ("json", "pdf"):
            report = client.post("/api/v1/reports", json={"snapshot": data, "format": kind})
            assert report.status_code == 200, report.text
            if kind == "pdf":
                assert report.content.startswith(b"%PDF-")
            else:
                assert report.json()["analysis"]["extraction"]["candidate"]["name"] == "Alex Example"
