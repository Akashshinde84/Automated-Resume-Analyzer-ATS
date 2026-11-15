"""Optional actual PostgreSQL test. Uses only a fresh random schema, never public tables."""
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy import text
import pytest

from app.core.config import Settings
from app.db.session import Database, normalize_database_url
from app.main import create_app


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='TEST_POSTGRES_URL not configured; live PostgreSQL unavailable')
def test_actual_postgresql_roundtrip(docx_bytes):
    # Dedicated temporary schema isolates test DDL/data from all other schemas.
    admin = Database(os.environ['TEST_POSTGRES_URL'])
    schema = 'ats_test_' + uuid4().hex
    with admin.engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        url = normalize_database_url(os.environ['TEST_POSTGRES_URL']).update_query_dict({'options':f'-c search_path={schema}'}).render_as_string(hide_password=False)
        config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
        config.attributes['database_url'] = url
        command.upgrade(config,'head')
        command.check(config)
        token = 'postgres-test-' + 'a' * 40
        settings = Settings(_env_file=None,app_mode='single_user',single_user_api_key=token,
                            storage_enabled=True,database_url=url,spacy_model='missing_postgres_test_model')
        with TestClient(create_app(settings),headers={'Authorization':'Bearer '+token}) as client:
            response = client.post('/api/v1/resumes/analyze?store=true',files={'file':('test.docx',docx_bytes)})
            assert response.status_code == 200
            ident = response.json()['id']
            response = client.post('/api/v1/jobs/match',json={'analysis_id':ident,'job_description':'Required: Python','store':True})
            assert response.status_code == 200
            assert client.get('/api/v1/analyses/' + ident).json()['match_count'] == 1
            assert client.delete('/api/v1/analyses/' + ident).status_code == 204
            assert client.get('/api/v1/analyses').json()['total'] == 0
        command.downgrade(config,'base')
    finally:
        with admin.engine.begin() as connection:
            connection.execute(DropSchema(schema,cascade=True))
        admin.dispose()


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='TEST_POSTGRES_URL not configured; live PostgreSQL permissions unavailable')
def test_restricted_runtime_role_permissions():
    """CI-only privilege probe. Does not certify a deployment's configured role."""
    admin = Database(os.environ['TEST_POSTGRES_URL'])
    schema, role = 'ats_perm_' + uuid4().hex, 'ats_role_' + uuid4().hex
    created_role = False
    try:
        with admin.engine.begin() as connection:
            connection.execute(CreateSchema(schema))
            # Both identifiers are generated hex-only values, not user input.
            connection.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
            created_role = True
            connection.exec_driver_sql(f'CREATE TABLE "{schema}".probe (id integer PRIMARY KEY)')
            connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
            connection.exec_driver_sql(f'GRANT SELECT, INSERT, UPDATE, DELETE ON "{schema}".probe TO "{role}"')
            assert connection.scalar(text('SELECT has_schema_privilege(:role,:schema,\'USAGE\')'), {'role':role,'schema':schema})
            assert not connection.scalar(text('SELECT has_schema_privilege(:role,:schema,\'CREATE\')'), {'role':role,'schema':schema})
            for privilege in ['SELECT','INSERT','UPDATE','DELETE']:
                assert connection.scalar(text('SELECT has_table_privilege(:role,:table,:privilege)'), {'role':role,'table':schema+'.probe','privilege':privilege})
            assert not connection.scalar(text('SELECT has_table_privilege(:role,:table,\'TRUNCATE\')'), {'role':role,'table':schema+'.probe'})
            flags = connection.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=:role'), {'role':role}).one()
            assert flags == (False,False,False)
    finally:
        with admin.engine.begin() as connection:
            connection.execute(DropSchema(schema,cascade=True,if_exists=True))
            if created_role:
                connection.exec_driver_sql(f'DROP ROLE "{role}"')
        admin.dispose()
