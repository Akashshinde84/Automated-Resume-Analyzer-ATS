"""Ontology, contextual matching and additive parser integration regressions."""
from io import BytesIO
import json
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.core.config import Settings
from app.main import create_app
from app.schemas.skills import SkillOntology
from app.services.parser import ResumeParser
from app.services.skills import ONTOLOGY_PATH, SkillExtractor


@pytest.fixture(scope="module")
def extractor():
    return SkillExtractor()


def names(extractor, text):
    return [skill.name for skill in extractor.extract(text)]


@pytest.mark.parametrize("alias,canonical", [
    ("React", "React"), ("React.js", "React"), ("ReactJS", "React"),
    ("JS", "JavaScript"), ("JavaScript", "JavaScript"),
    ("ML", "Machine Learning"), ("Machine Learning", "Machine Learning"),
    ("Postgres", "PostgreSQL"), ("AWS", "Amazon Web Services"),
    ("sklearn", "scikit-learn"), ("Team Collaboration", "Teamwork"),
])
def test_aliases(extractor, alias, canonical):
    assert names(extractor, f"Skills: {alias}") == [canonical]


def test_all_required_categories_in_ontology(extractor):
    assert {s.category for s in extractor.ontology.skills} == {
        "technical", "programming_languages", "frameworks", "databases", "cloud_tools",
        "data_science", "machine_learning", "soft_skills",
    }


def test_no_substring_matches(extractor):
    assert names(extractor, "Skills: JavaScript, MySQL, TypeScript") == ["JavaScript", "MySQL", "TypeScript"]
    assert names(extractor, "Skills: JavaScripted, NoPython, JavaScript_React, PostgreSQLish") == []


def test_punctuation_and_longest_phrase(extractor):
    text = "Skills: C++/C#; .NET, Node.js (React.js), React Native, scikit-learn, CI/CD"
    result = names(extractor, text)
    assert result == ["C++", "C#", ".NET", "Node.js", "React", "React Native", "scikit-learn", "CI/CD"]
    assert names(extractor, "Skills: React Native") == ["React Native"]
    assert names(extractor, "Skills: GitHub Actions") == ["GitHub Actions"]


def test_unicode_and_whitespace_offsets(extractor):
    text = "技能：Python、React.js；José\nSkills: Machine\u00a0Learning, Problem-Solving\nProjects\nBuilt data tools using NumPy."
    skills = extractor.extract(text)
    assert [s.name for s in skills] == ["Python", "React", "Machine Learning", "Problem Solving", "NumPy"]
    for skill in skills:
        for span in skill.occurrences:
            assert text[span.start:span.end] == span.text
    assert names(extractor, "Skills: Python\u0301, JavaScripté, 非Python文字") == []


def test_deduplicates_preserving_every_occurrence_and_source(extractor):
    text = "Skills: JS, JavaScript, ReactJS\nExperience\nBuilt JavaScript applications.\nProjects: React.js\nTechnical Skills: JS"
    skills = extractor.extract(text)
    javascript = skills[0]
    assert javascript.name == "JavaScript"
    assert javascript.explicitly_listed
    assert [o.source_type for o in javascript.occurrences] == ["explicit", "explicit", "experience", "explicit"]
    assert len(skills) == 2
    react = skills[1]
    assert [o.section for o in react.occurrences] == ["skills", "projects"]
    assert [o.source_type for o in react.occurrences] == ["explicit", "project"]


def test_mentions_not_promoted_to_explicit_skills(extractor):
    text = "Summary\nPython developer\nEducation\nSQL course\nWork History\nUsed PostgreSQL\nProjects\nBuilt with FastAPI"
    skills = extractor.extract(text)
    assert all(not s.explicitly_listed for s in skills)
    assert skills[0].occurrences[0].source_type == "other"
    assert skills[2].occurrences[0].source_type == "experience"
    assert skills[3].occurrences[0].source_type == "project"


@pytest.mark.parametrize("text", [
    "Go to school and react quickly.", "Skills\nGo to market\nR & D activities",
    "Experience\nWe go to meetings every day.\nR&D department",
    "Summary\nMeasured 5 ml of water.", "Contact\nR Smith",
])
def test_ambiguous_terms_rejected(extractor, text):
    assert names(extractor, text) == []


@pytest.mark.parametrize("text,expected", [
    ("Skills: R, Go, C", ["R", "Go", "C"]),
    ("Skills\nGo\nR\nC", ["Go", "R", "C"]),
    ("Experience\nBuilt backend services in Go.", ["Go"]),
    ("Projects\nPerformed statistical analysis using R.", ["Statistical Analysis", "R"]),
    ("Projects\nDeveloped applications using C.", ["C"]),
    ("Golang and R programming", ["Go", "R"]),
    ("Experience\nDeveloped ML pipelines.", ["Machine Learning"]),
])
def test_ambiguous_terms_require_context(extractor, text, expected):
    assert names(extractor, text) == expected
    assert all(s.occurrences[0].context_rule for s in extractor.extract("Skills: R, Go, C"))


@pytest.mark.parametrize("text", ["", "Skills", "Skills:\n\nExperience\n\nProjects", "Technical Skills:\nEducation"])
def test_empty_sections(extractor, text):
    assert extractor.extract(text) == []


def test_no_matches_inside_urls_email_or_qualified_identifiers(extractor):
    text = "https://example.test/Python/Java\npython@example.test\nwww.react.js/Go\nthing.Python\nPython.txt"
    assert names(extractor, text) == []


def test_repeated_sections_and_crlf_offsets(extractor):
    text = "Skills: Python\r\nExperience\r\nUsed SQL\r\nSkills: SQL\r\n"
    skills = extractor.extract(text)
    assert skills[1].explicitly_listed
    assert [s.section for s in skills[1].occurrences] == ["experience", "skills"]
    assert all(text[s.start:s.end] == s.text for skill in skills for s in skill.occurrences)


def test_ontology_validation_rejects_collisions_and_unknown_fields():
    data = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
    data["skills"].append({"name": "Other Skill", "category": "technical", "aliases": ["jS"]})
    with pytest.raises(ValidationError, match="collide"):
        SkillOntology.model_validate(data)
    with pytest.raises(ValidationError):
        SkillOntology.model_validate({"version": "1.0.0", "skills": [{"name": "X", "category": "made_up"}]})
    with pytest.raises(ValidationError):
        SkillOntology.model_validate({"version": "1.0.0", "skills": [{"name": "X", "category": "technical", "ambiguous_aliases": ["X"]}]})


def test_custom_unicode_alias_and_literal_metacharacters(tmp_path):
    path = tmp_path / "skills.json"
    path.write_text(json.dumps({"version": "1.0.1", "skills": [
        {"name": "Communication", "category": "soft_skills", "aliases": ["沟通"]},
        {"name": "Example++", "category": "technical", "aliases": []},
    ]}, ensure_ascii=False), encoding="utf-8")
    custom = SkillExtractor(path)
    assert names(custom, "Skills: 沟通, Example++") == ["Communication", "Example++"]
    assert names(custom, "Skills: Example, Example++ish") == []


def test_pdf_parser_adds_json_serializable_skills(tmp_path, make_pdf):
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(make_pdf(["Technical Skills: JS, React.js", "Experience", "Built Python services."]))
    result = ResumeParser().parsefile(path)
    assert result["skill_ontology_version"] == "1.0.0"
    assert [s["name"] for s in result["skills"]] == ["JavaScript", "React", "Python"]
    assert result["skills"][0]["explicitly_listed"]
    assert not result["skills"][2]["explicitly_listed"]
    assert all(result["text"][o["start"]:o["end"]] == o["text"] for s in result["skills"] for o in s["occurrences"])
    json.dumps(result)


def test_docx_upload_returns_skill_evidence(docx_bytes):
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.post("/api/v1/resumes/parse-text", files={"file": ("synthetic.docx", docx_bytes)})
    assert response.status_code == 200
    result = response.json()
    assert [s["name"] for s in result["skills"]] == ["Python", "SQL", "React"]
    assert result["skills"][0]["explicitly_listed"]
    assert result["skills"][2]["occurrences"][0]["section"] == "projects"


def test_empty_pdf_has_empty_skills(tmp_path, make_pdf):
    path = tmp_path / "empty.pdf"
    path.write_bytes(make_pdf())
    assert ResumeParser().parsefile(path)["skills"] == []


def test_ambiguous_aliases_with_unicode_delimiters(extractor):
    assert names(extractor, "Skills: Go、R，C；ML") == ["Go", "R", "C", "Machine Learning"]


def test_framework_project_cell_and_cloud_verb_disambiguation(extractor):
    assert names(extractor, "Projects\nReact") == ["React"]
    assert names(extractor, "Experience\nBuilt using React.") == ["React"]
    assert names(extractor, "Experience\nRender images in Python.") == ["Python"]
    assert names(extractor, "Experience\nDeployed the app to Render.") == ["Render"]


def test_matches_without_ner_model(extractor, monkeypatch):
    # Skill service has no NER/model loader dependency.
    def unavailable(*args, **kwargs):
        raise AssertionError("Skill extraction must not load spaCy models")
    monkeypatch.setattr("spacy.load", unavailable)
    assert names(extractor, "Skills: JS, Go, R") == ["JavaScript", "Go", "R"]
