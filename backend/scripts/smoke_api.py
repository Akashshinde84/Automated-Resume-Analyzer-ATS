"""Real HTTP check with a throwaway migrated SQLite DB, synthetic data and random token.

Always overrides the subprocess DB config; never operates on production records.
"""
from io import BytesIO
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

import httpx
from alembic import command
from alembic.config import Config
from docx import Document

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def main():
    with TemporaryDirectory(prefix='ats-smoke-') as directory:
        url = 'sqlite:///' + (Path(directory) / 'smoke.db').as_posix()
        config = Config(str(BACKEND / 'alembic.ini'))
        config.attributes['database_url'] = url
        command.upgrade(config, 'head')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        token = secrets.token_urlsafe(48)
        environment = {**os.environ, 'APP_MODE':'single_user', 'SINGLE_USER_API_KEY':token,
            'SINGLE_USER_ID':'smoke-owner', 'STORAGE_ENABLED':'true', 'DATABASE_URL':url,
            'REQUIRE_NER_MODEL':'false', 'SPACY_MODEL':'missing_smoke_model',
            'ALLOWED_HOSTS':'["localhost","127.0.0.1"]'}
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
            '--port', str(port), '--no-access-log'], cwd=BACKEND, env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=15) as client:
                ready = False
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Server exited')
                    try:
                        ready = client.get('/health').status_code == 200
                    except httpx.TransportError:
                        pass
                    if ready:
                        break
                    time.sleep(.1)
                assert ready
                assert client.get('/api/v1/analyses').status_code == 401
                client.headers['Authorization'] = 'Bearer ' + token
                document = Document()
                for line in ['Name: Synthetic Example','Skills: Python, SQL','Experience','Built Python APIs.']:
                    document.add_paragraph(line)
                stream = BytesIO()
                document.save(stream)
                response = client.post('/api/v1/resumes/analyze?store=true',files={'file':('synthetic.docx',stream.getvalue())})
                assert response.status_code == 200
                ident = response.json()['id']
                response = client.post('/api/v1/jobs/match',json={'analysis_id':ident,'job_description':'Required: Python, SQL','store':True})
                assert response.status_code == 200 and response.json()['stored']
                assert client.get('/api/v1/analyses/' + ident).json()['match_count'] == 1
                assert client.get('/api/v1/analyses').json()['total'] == 1
                assert client.delete('/api/v1/analyses/' + ident).status_code == 204
                assert client.get('/api/v1/analyses/' + ident).status_code == 404
                assert client.get('/api/v1/analyses').json()['total'] == 0
                print(json.dumps({'health':200,'unauthorized_history':401,'analyze':200,'stored_match':200,
                    'retrieve':200,'list':200,'delete':204,'deleted_lookup':404,'remaining_records':0}))
        finally:
            if os.name == 'nt':
                # The Windows venv launcher can spawn a child interpreter. Stop
                # only the exact process tree this check created, before unlinking DB files.
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'Isolated local HTTP smoke check failed ({type(exc).__name__}); no input or credentials logged.', file=sys.stderr)
        raise SystemExit(1) from None
