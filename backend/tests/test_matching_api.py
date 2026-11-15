from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.core.config import Settings
from app.main import create_app
from app.schemas.matching import MatchingResponse, MatchingWeights
from app.services.matching import MatchingService

URL = "/api/v1/resumes/match"


@pytest.fixture
def client():
    with TestClient(create_app(Settings(_env_file=None))) as connection:
        yield connection


def test_typed_match_api_and_parser_bridge(client, docx_bytes):
    parsed = client.post('/api/v1/resumes/parse-text', files={'file': ('synthetic.docx', docx_bytes)}).json()
    response = client.post(URL, json={'resume': parsed, 'job_description': 'Required: Python, SQL; Preferred: Docker'})
    assert response.status_code == 200
    result = MatchingResponse.model_validate(response.json())
    assert result.status == 'computed'
    assert result.scores.skill_overlap == 80
    assert [skill.name for skill in result.matched_skills] == ['Python', 'SQL']
    assert 'Python' in result.matched_skills[0].resume_evidence[0].context


@pytest.mark.parametrize('payload', [
    {}, {'resume': {'text': 'PRIVATE'}, 'job_description': []},
    {'resume': {'text': 'PRIVATE' * 17000}, 'job_description': 'Python'},
    {'resume': {'text': 'Python'}, 'job_description': 'PRIVATE' * 9000},
    {'resume': {'text': 'PRIVATE'}, 'job_description': 'Python', 'weights': {'skills': .3, 'text': .3}},
    {'resume': {'text': 'PRIVATE'}, 'job_description': 'Python', 'decision': 'hire'},
])
def test_validation_never_echoes_sensitive_input(client, payload, caplog):
    response = client.post(URL, json=payload)
    assert response.status_code == 422
    assert 'PRIVATE' not in response.text + caplog.text
    assert '"input"' not in response.text


def test_body_limit_covers_chunked_json(client):
    response = client.post(URL, content=iter([b'x' * 1_100_000, b'y' * 1_100_000]), headers={'Content-Type': 'application/json'})
    assert response.status_code == 413


def test_matching_error_never_logs_input(client, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise RuntimeError('PRIVATE jane@example.test')
    monkeypatch.setattr(MatchingService, 'match', fail)
    response = client.post(URL, json={'resume': {'text': 'PRIVATE'}, 'job_description': 'PRIVATE'})
    assert response.status_code == 503
    assert 'PRIVATE' not in response.text + caplog.text
    assert 'jane@example.test' not in response.text + caplog.text


def test_configured_defaults_and_request_override():
    settings = Settings(_env_file=None, matching_weights=MatchingWeights(skills=1, text=0))
    with TestClient(create_app(settings)) as client:
        body = {'resume': {'text': 'Skills: Python'}, 'job_description': 'Required: Python, SQL'}
        result = client.post(URL, json=body).json()
        assert result['scores']['overall'] == result['scores']['skill_overlap']
        body['weights'] = {'skills': 0, 'text': 1}
        result = client.post(URL, json=body).json()
        assert result['scores']['overall'] == result['scores']['text_similarity']


def test_weights_environment(monkeypatch):
    monkeypatch.setenv('MATCHING_WEIGHTS', '{"skills":0.6,"text":0.4}')
    assert Settings(_env_file=None).matching_weights.skills == .6


def test_openapi_and_no_decisions(client):
    schema = client.get('/openapi.json').json()
    response = schema['paths'][URL]['post']['responses']['200']['content']['application/json']['schema']
    assert response['$ref'].endswith('/MatchingResponse')
    assert 'decision' not in schema['components']['schemas']['MatchingResponse']['properties']
