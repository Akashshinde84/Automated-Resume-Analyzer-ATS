"""Rubric arithmetic, evidence, fairness constraints, integrity and integration."""
from copy import deepcopy
from io import BytesIO

from fastapi.testclient import TestClient
from pdfminer.high_level import extract_text
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.schemas.analysis import ParsedResumeData
from app.schemas.readiness import ReadinessWeights
from app.services.extraction import InformationExtractor
from app.services.parser import ResumeParser
from app.services.readiness import ReadinessService
from test_extraction import StubNER


FULL = ["Name: Alex Example", "alex@example.test", "Skills", "Python, SQL",
        "Education", "Example University", "BSc in Computer Science", "Projects",
        "Project: Document Tool", "- Built Python and SQL APIs that processed 200 records for a research team."]


def evaluate(tmp_path, make_pdf, lines=FULL, weights=None):
    path = tmp_path / "fictional.pdf"
    path.write_bytes(make_pdf(lines))
    parsed = ParsedResumeData.model_validate(ResumeParser().parsefile(path))
    extraction = InformationExtractor(StubNER()).extract(parsed.text)
    return ReadinessService(weights).evaluate(parsed, extraction)


def test_documented_full_rubric_and_evidence(tmp_path, make_pdf):
    result = evaluate(tmp_path, make_pdf)
    assert result.score == 100
    assert [c.maximum for c in result.categories] == [10, 20, 15, 20, 10, 15, 10]
    assert result.score == sum(c.score for c in result.categories)
    assert not result.recommendations
    assert next(c for c in result.categories if c.key == 'clarity').checks[1].evidence


def test_fresher_projects_equal_equivalent_professional_work(tmp_path, make_pdf):
    project = evaluate(tmp_path, make_pdf)
    work = evaluate(tmp_path, make_pdf, [line.replace('Projects', 'Experience').replace('Project: Document Tool', 'Role: Software Engineer') for line in FULL])
    assert project.score == work.score


def test_optional_links_and_personal_details_do_not_affect_score(tmp_path, make_pdf):
    original = evaluate(tmp_path, make_pdf)
    changed = evaluate(tmp_path, make_pdf, [FULL[0], 'Gender: female', 'Age: 24', 'Nationality: Example', *FULL[1:]])
    with_links = evaluate(tmp_path, make_pdf, [FULL[0], 'https://github.com/example', *FULL[1:]])
    assert original.score == changed.score == with_links.score


def test_dates_are_not_measurable_achievements(tmp_path, make_pdf):
    result = evaluate(tmp_path, make_pdf, [line.replace('200 records', 'records') for line in FULL] + ['2021 - 2025'])
    check = next(c for c in result.categories if c.key == 'clarity').checks[1]
    assert check.earned == 0
    suggestion = next(r for r in result.recommendations if r.code == 'measured_outcome')
    assert suggestion.possible_points == 4
    assert 'Never invent numbers' in suggestion.suggestion


def test_empty_scan_has_no_score(tmp_path, make_pdf):
    result = evaluate(tmp_path, make_pdf, [])
    assert result.score is None and result.status == 'insufficient_text'
    assert result.recommendations[0].code == 'no_text'


def test_custom_weights_validate_and_use_same_criteria(tmp_path, make_pdf):
    with pytest.raises(ValidationError):
        ReadinessWeights(contact=20)
    weights = ReadinessWeights(contact=20, structure=10)
    result = evaluate(tmp_path, make_pdf, weights=weights)
    assert result.categories[0].maximum == 20 and result.score == 100


def test_weak_records_and_duplicate_contributions_have_specific_recommendations(tmp_path, make_pdf):
    result = evaluate(tmp_path, make_pdf, ['Skills', 'Python', 'Projects', 'Project: Tool', '- Built APIs.', '- Built APIs.'])
    codes = {r.code for r in result.recommendations}
    assert {'record_detail', 'reachable_contact', 'unique_descriptions', 'qualification_detail'} <= codes
    assert [r.priority for r in result.recommendations] == sorted([r.priority for r in result.recommendations], key={'high':0,'medium':1,'low':2}.get)


def test_negated_skills_are_not_readiness_evidence(tmp_path, make_pdf):
    result = evaluate(tmp_path, make_pdf, ['Skills', 'No Python experience', 'Projects', 'Project: Tool', '- Built a document parser for a classroom activity.'])
    check = next(c for c in result.categories if c.key == 'skills').checks[0]
    assert check.earned == 0


def test_anonymous_readiness_reports_and_tamper_rejection(make_pdf):
    with TestClient(create_app(Settings(_env_file=None, app_mode='anonymous', isolate_parsing=True))) as client:
        response = client.post('/api/v1/resumes/analyze', files={'file':('fictional.pdf',make_pdf(FULL))})
        assert response.status_code == 200
        data = response.json()
        assert data['readiness']['score'] == 100
        report = client.post('/api/v1/reports', json={'snapshot':data,'format':'json'})
        assert report.status_code == 200
        assert report.json()['analysis']['readiness'] == data['readiness']
        changed = deepcopy(data)
        changed['readiness']['score'] = 1
        assert client.post('/api/v1/reports', json={'snapshot':changed,'format':'json'}).status_code == 409
        pdf = client.post('/api/v1/reports', json={'snapshot':data,'format':'pdf'})
        assert pdf.status_code == 200
        assert 'ATS readiness' in extract_text(BytesIO(pdf.content))


def test_job_match_has_separate_score_and_project_support():
    from app.services.matching import MatchingService
    text = '\n'.join(FULL)
    result = MatchingService().match({'text':text}, 'Required skills: Python, SQL. Preferred: Docker.')
    assert result.scores.overall is not None
    assert [skill.name for skill in result.matched_skills] == ['Python', 'SQL']
    assert result.supporting_records[0].name == 'Document Tool'
    assert result.supporting_records[0].skills == ['Python', 'SQL']
    assert all(text[e.start:e.end] == e.text for e in result.supporting_records[0].evidence)
    assert any(suggestion.skill == 'Docker' and 'do not list' in suggestion.message for suggestion in result.suggestions)
