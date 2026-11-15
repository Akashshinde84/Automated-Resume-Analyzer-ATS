"""Phase 6 API tests using real Alembic migrations and isolated SQLite databases."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError
import pytest

from app.core.config import Settings
from app.db.models import Analysis, JobDescription, MatchResult, StructuredResume
from app.db.repository import AnalysisRepository, utcnow
from app.main import create_app
from app.services.extraction import InformationExtractor

TOKEN = 'test-only-' + 'a' * 40
BACKEND = Path(__file__).resolve().parents[1]
AUTH = {'Authorization': 'Bearer ' + TOKEN}


def migration_config(url):
    config = Config(str(BACKEND / 'alembic.ini'))
    config.attributes['database_url'] = url
    return config


@pytest.fixture
def database_url(tmp_path):
    url = 'sqlite:///' + (tmp_path / 'isolated.db').as_posix()
    config = migration_config(url)
    command.upgrade(config, 'head')
    yield url


def settings(**kwargs):
    return Settings(_env_file=None, app_mode='single_user', single_user_api_key=TOKEN,
                    spacy_model='not_installed_phase6_test_model', **kwargs)


@pytest.fixture
def client(database_url):
    application = create_app(settings(storage_enabled=True, database_url=database_url))
    with TestClient(application, headers=AUTH) as connection:
        yield connection


def analyze(client, content, store=True):
    return client.post('/api/v1/resumes/analyze', params={'store': str(store).lower()}, files={'file': ('synthetic.docx', content)})


def counts(client):
    with client.app.state.database.sessions() as session:
        return [session.scalar(select(func.count()).select_from(model)) for model in (Analysis, StructuredResume, JobDescription, MatchResult)]


def test_analysis_match_get_list_delete_flow(client, docx_bytes):
    response = analyze(client, docx_bytes)
    assert response.status_code == 200
    data = response.json()
    assert data['stored'] and data['id'] and data['expires_at']
    assert data['parsed']['skills'][0]['name'] == 'Python'
    assert data['extraction']['candidate']['emails'] == ['jose@example.test']
    assert data['extraction']['nlp']['status'] == 'unavailable'
    ident = data['id']
    match = client.post('/api/v1/jobs/match', json={'analysis_id': ident, 'job_description': 'Required: Python, SQL; Preferred: Docker', 'store': True})
    assert match.status_code == 200
    assert match.json()['stored'] and match.json()['id']
    assert match.json()['result']['scores']['skill_overlap'] == 80
    assert counts(client) == [1, 1, 1, 1]
    detail = client.get('/api/v1/analyses/' + ident)
    assert detail.status_code == 200
    assert detail.json()['match_count'] == 1
    assert detail.json()['matches'][0]['job_description'].startswith('Required:')
    page = client.get('/api/v1/analyses?limit=1&offset=0').json()
    assert page['total'] == 1 and page['items'][0]['id'] == ident
    assert 'parsed' not in page['items'][0] and 'filename' not in page['items'][0]
    assert response.headers['cache-control'] == 'no-store'
    assert client.delete('/api/v1/analyses/' + ident).status_code == 204
    assert counts(client) == [0, 0, 0, 0]
    assert client.get('/api/v1/analyses/' + ident).status_code == 404
    assert client.delete('/api/v1/analyses/' + ident).status_code == 404


def test_stateless_mode_and_no_implicit_saving(client, docx_bytes):
    response = analyze(client, docx_bytes, store=False)
    assert response.status_code == 200
    assert response.json()['id'] is None and response.json()['expires_at'] is None
    assert not response.json()['stored']
    assert counts(client) == [0, 0, 0, 0]
    match = client.post('/api/v1/jobs/match', json={'resume': response.json()['parsed'], 'job_description': 'Required: Python'})
    assert match.status_code == 200 and not match.json()['stored']
    assert counts(client) == [0, 0, 0, 0]


def test_no_database_needed_when_storage_disabled(docx_bytes):
    with TestClient(create_app(settings())) as client:
        client.headers.update(AUTH)
        assert client.app.state.database is None
        assert analyze(client, docx_bytes, store=False).status_code == 200
        assert analyze(client, docx_bytes, store=True).status_code == 409
        assert client.get('/api/v1/analyses').status_code == 409
        assert client.post('/api/v1/jobs/match', json={'resume': {'text': 'Skills: Python'}, 'job_description': 'Required: Python'}).status_code == 200


@pytest.mark.parametrize('path,method', [('/api/v1/analyses','get'),('/api/v1/analyses/' + str(uuid4()),'delete'),('/api/v1/resumes/analyze','post'),('/api/v1/jobs/match','post'),('/api/v1/resumes/parse-text','post'),('/api/v1/resumes/extract','post'),('/api/v1/resumes/match','post')])
def test_all_v1_routes_require_auth_in_deployment(path, method):
    with TestClient(create_app(settings())) as client:
        response = getattr(client, method)(path)
        assert response.status_code == 401
        assert response.headers['www-authenticate'] == 'Bearer'
        assert response.headers['cache-control'] == 'no-store'
        response = getattr(client, method)(path, headers={'Authorization': 'Bearer wrong'})
        assert response.status_code == 401


def test_default_mode_fails_closed_without_key():
    with TestClient(create_app(Settings(_env_file=None, app_mode='single_user'))) as client:
        assert client.get('/health').json() == {'status': 'ok'}
        assert client.get('/api/v1/analyses').status_code == 503
        assert client.post('/api/v1/resumes/parse-text').status_code == 503
    with TestClient(create_app(Settings(_env_file=None, app_mode='local'))) as client:
        assert client.get('/api/v1/analyses').status_code == 503
        assert client.post('/api/v1/resumes/analyze').status_code == 503


def test_auth_before_body_read():
    read = []
    def body():
        read.append(True)
        yield b'x' * 10_000_000
    with TestClient(create_app(settings())) as client:
        response = client.post('/api/v1/resumes/analyze', content=body(), headers={'Content-Type':'multipart/form-data; boundary=test'})
    assert response.status_code == 401
    assert not read


def test_owner_authorization(client, database_url, docx_bytes):
    ident = analyze(client, docx_bytes).json()['id']
    other = create_app(settings(storage_enabled=True, database_url=database_url, single_user_id='different-owner'))
    with TestClient(other, headers=AUTH) as outsider:
        assert outsider.get('/api/v1/analyses').json()['total'] == 0
        assert outsider.get('/api/v1/analyses/' + ident).status_code == 404
        assert outsider.delete('/api/v1/analyses/' + ident).status_code == 404
        assert outsider.post('/api/v1/jobs/match', json={'analysis_id':ident, 'job_description':'Required: Python'}).status_code == 404
    assert client.get('/api/v1/analyses/' + ident).status_code == 200


def test_expiry_and_cascaded_retention(client, docx_bytes):
    ident = UUID(analyze(client, docx_bytes).json()['id'])
    client.post('/api/v1/jobs/match', json={'analysis_id':str(ident),'job_description':'Required: Python','store':True})
    with client.app.state.database.sessions.begin() as session:
        row = session.get(Analysis, ident)
        row.expires_at = utcnow() - timedelta(seconds=1)
    assert client.get('/api/v1/analyses/' + str(ident)).status_code == 404
    assert client.post('/api/v1/jobs/match', json={'analysis_id':str(ident),'job_description':'Required: Python'}).status_code == 404
    assert client.get('/api/v1/analyses').json()['total'] == 0
    assert counts(client) == [0,0,0,0]


def test_shorter_policy_applies_to_existing_rows(client, docx_bytes):
    ident = UUID(analyze(client, docx_bytes).json()['id'])
    with client.app.state.database.sessions.begin() as session:
        row = session.get(Analysis, ident)
        row.created_at = utcnow() - timedelta(days=3)
    config = client.app.state.settings.model_copy(update={'retention_days':1})
    repo = AnalysisRepository(client.app.state.database, config)
    assert repo.purge_expired() == 1
    assert counts(client) == [0,0,0,0]


def test_database_error_rollback_and_private_response(client, docx_bytes, caplog):
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.lower().startswith('insert into structured_resumes'):
            raise OperationalError(statement, parameters, RuntimeError('PRIVATE database credential leak'))
    engine = client.app.state.database.engine
    event.listen(engine, 'before_cursor_execute', fail)
    try:
        response = analyze(client, docx_bytes)
        assert response.status_code == 503
        assert 'PRIVATE' not in response.text + caplog.text
        assert 'jose@example.test' not in response.text + caplog.text
        assert counts(client) == [0,0,0,0]
    finally:
        event.remove(engine, 'before_cursor_execute', fail)


def test_model_fallback_and_strict_failure(docx_bytes):
    with TestClient(create_app(settings(require_ner_model=True)), headers=AUTH) as client:
        response = analyze(client, docx_bytes, store=False)
        assert response.status_code == 503
        assert response.json()['detail']['code'] == 'model_unavailable'


def test_model_inference_failure_private(client, docx_bytes, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise RuntimeError('PRIVATE jose@example.test')
    monkeypatch.setattr(InformationExtractor, 'extract', fail)
    response = analyze(client, docx_bytes)
    assert response.status_code == 503
    assert 'PRIVATE' not in response.text + caplog.text
    assert counts(client) == [0,0,0,0]


@pytest.mark.parametrize('payload', [
    {'resume':{'text':'Skills: Python'},'job_description':''},
    {'resume':{'text':'Skills: Python'},'job_description':'   '},
    {'resume':{'text':'Skills: Python'},'job_description':'PRIVATE'*8000},
    {'job_description':'Required: Python'},
    {'resume':{'text':'Skills: Python'},'analysis_id':str(uuid4()),'job_description':'Required: Python'},
    {'resume':{'text':'Skills: Python'},'store':True,'job_description':'Required: Python'},
])
def test_invalid_job_requests(client, payload, caplog):
    response = client.post('/api/v1/jobs/match', json=payload)
    assert response.status_code == 422
    assert 'PRIVATE' not in response.text + caplog.text


def test_limits_and_upload_validation(client, docx_bytes):
    assert client.get('/api/v1/analyses?limit=101').status_code == 422
    assert client.get('/api/v1/analyses?offset=-1').status_code == 422
    assert client.get('/api/v1/analyses/not-a-uuid').status_code == 422
    assert client.post('/api/v1/resumes/analyze', files={'file':('file.exe',b'bad')}).status_code == 415
    assert client.post('/api/v1/resumes/analyze', files={'file':('file.pdf',b'not pdf')}).status_code == 415
    assert client.post('/api/v1/resumes/analyze', files={'file':('file.pdf',b'')}).status_code == 422
    assert client.post('/api/v1/resumes/analyze', files={'file':('file.docx',docx_bytes)}, data={'phone_region':'XX'}).status_code == 422
    assert counts(client) == [0,0,0,0]


def test_history_bounds(database_url, docx_bytes):
    with TestClient(create_app(settings(storage_enabled=True,database_url=database_url,max_stored_analyses=1,max_matches_per_analysis=1)),headers=AUTH) as client:
        ident = analyze(client,docx_bytes).json()['id']
        assert analyze(client,docx_bytes).status_code == 409
        payload = {'analysis_id':ident,'job_description':'Required: Python','store':True}
        assert client.post('/api/v1/jobs/match',json=payload).status_code == 200
        assert client.post('/api/v1/jobs/match',json=payload).status_code == 409
        assert counts(client) == [1,1,1,1]


def test_cors_openapi_and_trusted_hosts(client):
    schema = client.get('/openapi.json').json()
    for path in ['/api/v1/resumes/analyze','/api/v1/jobs/match','/api/v1/analyses','/api/v1/analyses/{analysis_id}']:
        assert path in schema['paths']
    assert schema['paths']['/api/v1/resumes/analyze']['post']['security'] == [{'SingleUserBearer':[]}]
    body = schema['paths']['/api/v1/resumes/analyze']['post']['requestBody']['content']['multipart/form-data']['schema']
    assert body['properties']['file']['format'] == 'binary'
    response = client.options('/api/v1/analyses/' + str(uuid4()), headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'DELETE','Access-Control-Request-Headers':'authorization'})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
    assert client.options('/api/v1/analyses',headers={'Origin':'https://untrusted.test','Access-Control-Request-Method':'GET'}).status_code == 400
    assert client.get('/health',headers={'host':'untrusted.test'}).status_code == 400


def test_configuration_prevents_unsafe_storage():
    with pytest.raises(ValidationError):
        Settings(_env_file=None,storage_enabled=True,database_url='sqlite:///:memory:')
    with pytest.raises(ValidationError):
        Settings(_env_file=None,single_user_api_key='short')
    with pytest.raises(ValidationError):
        Settings(_env_file=None,app_mode='multi_user')
    with pytest.raises(ValidationError):
        Settings(_env_file=None,allowed_hosts=['*'])
    with pytest.raises(ValidationError):
        Settings(_env_file=None,allowed_hosts=['*.example.test'])
    with pytest.raises(ValidationError):
        Settings(_env_file=None,cors_origins=['https://*.example.test'])


def test_processing_concurrency_before_parsing(docx_bytes, monkeypatch):
    from app.api import resumes
    entered, release = Event(), Event()
    original = resumes._parse_upload
    def hold(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(resumes,'_parse_upload',hold)
    with TestClient(create_app(settings(max_concurrent_processing=1)),headers=AUTH) as client:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(analyze,client,docx_bytes,False)
            try:
                assert entered.wait(3)
                response = client.post('/api/v1/jobs/match',json={'resume':{'text':'Skills: Python'},'job_description':'Required: Python'})
                assert response.status_code == 429
                assert response.headers['retry-after'] == '2'
            finally:
                release.set()
            assert future.result().status_code == 200


def test_migrations_upgrade_check_downgrade(database_url):
    config = migration_config(database_url)
    command.check(config)
    command.downgrade(config,'base')
    command.upgrade(config,'head')
    command.check(config)


def test_postgresql_migration_sql():
    stream = StringIO()
    config = migration_config('postgresql+psycopg://unused:unused@localhost/unused_test')
    config.output_buffer = stream
    command.upgrade(config,'head',sql=True)
    sql = stream.getvalue()
    assert 'JSONB' in sql and 'UUID' in sql and 'ON DELETE CASCADE' in sql
    assert 'unused:unused' not in sql


def test_saved_match_pagination(client, docx_bytes):
    ident = analyze(client, docx_bytes).json()['id']
    for job in ['Required: Python', 'Required: SQL']:
        assert client.post('/api/v1/jobs/match', json={'analysis_id':ident,'job_description':job,'store':True}).status_code == 200
    first = client.get('/api/v1/analyses/' + ident + '?match_limit=1&match_offset=0').json()
    second = client.get('/api/v1/analyses/' + ident + '?match_limit=1&match_offset=1').json()
    assert first['match_count'] == second['match_count'] == 2
    assert len(first['matches']) == len(second['matches']) == 1
    assert first['matches'][0]['id'] != second['matches'][0]['id']
    assert client.get('/api/v1/analyses/' + ident + '?match_limit=51').status_code == 422


def test_unforeseen_errors_do_not_reach_server_tracebacks(client, docx_bytes, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise RuntimeError('PRIVATE jose@example.test')
    monkeypatch.setattr(AnalysisRepository,'save',fail)
    response = analyze(client,docx_bytes)
    assert response.status_code == 500
    assert response.json()['detail']['code'] == 'internal_error'
    assert 'PRIVATE' not in response.text + caplog.text
    assert 'jose@example.test' not in response.text + caplog.text


def test_periodic_retention_worker_is_started(database_url, monkeypatch):
    called = Event()
    original = AnalysisRepository.purge_expired
    def record(self):
        called.set()
        return original(self)
    monkeypatch.setattr(AnalysisRepository,'purge_expired',record)
    with TestClient(create_app(settings(storage_enabled=True,database_url=database_url,retention_cleanup_interval_seconds=1)),headers=AUTH):
        assert called.wait(3)
