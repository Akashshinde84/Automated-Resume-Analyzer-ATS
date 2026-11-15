"""Adversarial/privacy regressions with generated inputs, never real candidate data."""
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.parser import ResumeParser
from test_production_api import AUTH, client, database_url, settings  # noqa: F401


@pytest.mark.parametrize("mime", ["text/html", "application/x-msdownload", "application/octet-stream"])
def test_actual_signature_is_authoritative_not_spoofable_mime(client, docx_bytes, mime):
    good = client.post('/api/v1/resumes/analyze', files={'file': ('../../resume.docx', docx_bytes, mime)})
    assert good.status_code == 200 and good.json()['parsed']['metadata']['filename'] == 'resume.docx'
    wrong = client.post('/api/v1/resumes/analyze', files={'file': ('resume.pdf', b'<script>bad()</script>', 'application/pdf')})
    assert wrong.status_code == 415


@pytest.mark.parametrize("kind", ['corrupt', 'encrypted', 'scan', 'empty'])
def test_integrated_bad_documents_cleanup_and_private_logs(client, make_pdf, monkeypatch, caplog, kind):
    paths = []
    original = ResumeParser.parsefile
    def capture(self, path):
        paths.append(Path(path))
        return original(self, path)
    monkeypatch.setattr(ResumeParser, 'parsefile', capture)
    data = {'corrupt': b'%PDF-invalid PRIVATE secret@example.test', 'encrypted': make_pdf(['PRIVATE secret@example.test'], encrypted=True),
            'scan': make_pdf(image=True), 'empty': b''}[kind]
    response = client.post('/api/v1/resumes/analyze', files={'file': ('resume.pdf', data, 'application/pdf')})
    assert response.status_code == (200 if kind == 'scan' else 422)
    assert paths and all(not path.exists() and not path.parent.exists() for path in paths)
    assert 'secret@example.test' not in caplog.text + response.text


def test_docx_entity_payload_is_not_resolved_or_logged(client, docx_bytes, caplog):
    stream = BytesIO()
    with ZipFile(BytesIO(docx_bytes)) as original, ZipFile(stream, 'w', ZIP_DEFLATED) as malicious:
        for item in original.infolist():
            content = original.read(item.filename)
            if item.filename == 'word/document.xml':
                content = b'''<?xml version="1.0"?><!DOCTYPE w:document [<!ENTITY xxe SYSTEM "file:///nonexistent-private-qa-file">]><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>&xxe;</w:t></w:r></w:p></w:body></w:document>'''
            malicious.writestr(item.filename, content)
    response = client.post('/api/v1/resumes/analyze', files={'file': ('entity.docx', stream.getvalue())})
    assert response.status_code in {200, 422}
    if response.status_code == 200:
        assert response.json()['parsed']['text'] == ''
    assert 'nonexistent-private-qa-file' not in caplog.text + response.text


def test_large_and_unsigned_reports_fail_before_processing(client, make_pdf):
    large = b'%PDF-' + b' ' * (10 * 1024 * 1024)
    assert client.post('/api/v1/resumes/analyze', files={'file':('large.pdf',large)}).status_code == 413
    with TestClient(create_app(settings(max_upload_bytes=128)), headers=AUTH) as limited:
        assert limited.post('/api/v1/resumes/analyze', files={'file': ('r.pdf', make_pdf(['Text']))}).status_code == 413
    assert client.post('/api/v1/reports', json={'format':'json','analysis_id':'not-a-uuid'}).status_code == 422
    assert client.post('/api/v1/jobs/match', json={'resume':{'text':'Skills: Python'},'job_description':' '*8}).status_code == 422


def test_privacy_headers_cors_and_invalid_auth(client):
    for path in ['/api/v1/analyses', '/api/v1/reports', '/api/v1/resumes/analyze', '/api/v1/jobs/match']:
        response = client.request('GET' if path.endswith('analyses') else 'POST', path, headers={'Authorization':'Bearer invalid'})
        assert response.status_code == 401
        assert 'no-store' in response.headers['cache-control']
    result = client.options('/api/v1/reports', headers={'Origin':'https://attacker.test','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization'})
    assert result.status_code == 400 and 'access-control-allow-origin' not in result.headers
