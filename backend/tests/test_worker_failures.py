"""Reproducible decoder faults; no private PDFs or destructive in-process limits."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

from app.core.config import Settings
from app.services.parser import ResumeParser, ResumeParseError
from app.services.isolated_parser import parse_isolated


def test_pdf_worker_never_imports_nlp_stack(tmp_path,make_pdf):
    path=tmp_path/'synthetic.pdf';path.write_bytes(make_pdf(['Skills','Python']))
    code="""import sys
sys.path.insert(0,sys.argv[1])
class Guard:
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'spacy','torch','sklearn'}: raise RuntimeError('Heavy NLP import attempted by decoder')
sys.meta_path.insert(0,Guard())
from app.services.parser import ResumeParser
assert 'Python' in ResumeParser().parsefile(sys.argv[2])['text']
assert 'spacy' not in sys.modules
"""
    result=subprocess.run([sys.executable,'-I','-c',code,str(Path(__file__).resolve().parents[1]),str(path)],capture_output=True,timeout=15)
    assert result.returncode==0


@pytest.mark.parametrize('exit_code,code,status',[(2,'parsing_limits_unavailable',503),(3,'parsing_worker_failed',500),
    (4,'parsing_memory_limit',422),(6,'parsing_initialization_failed',503),(7,'parsing_output_limit',413),
    (8,'parsing_io_failed',503),(-9,'parsing_worker_terminated',503)])
def test_worker_exit_classification_and_private_logs(tmp_path,monkeypatch,caplog,exit_code,code,status):
    path=tmp_path/'PRIVATE-NAME.pdf';path.write_bytes(b'%PDF-')
    def failure(command,**kwargs):
        result_path=Path(command[4]);diag=result_path.with_suffix('.diagnostic.json')
        diag.write_text(json.dumps({'stage':'decode','exception_type':'MemoryError','message':'PRIVATE-RESUME-TEXT'}))
        return SimpleNamespace(returncode=exit_code)
    monkeypatch.setattr('app.services.isolated_parser.execute_decoder',failure)
    with pytest.raises(ResumeParseError) as exc:parse_isolated(path,ResumeParser(),Settings(_env_file=None))
    assert (exc.value.code,exc.value.status_code)==(code,status)
    assert exc.value.diagnostic_id in caplog.text
    assert 'PRIVATE' not in caplog.text
    assert not list(tmp_path.glob('*.json'))


def test_missing_and_invalid_result_are_server_errors(tmp_path,monkeypatch):
    path=tmp_path/'resume.pdf';path.write_bytes(b'%PDF-')
    monkeypatch.setattr('app.services.isolated_parser.execute_decoder',lambda *a,**k:SimpleNamespace(returncode=0))
    with pytest.raises(ResumeParseError) as exc:parse_isolated(path,ResumeParser(),Settings(_env_file=None))
    assert exc.value.code=='parsing_result_missing' and exc.value.status_code==500
    def invalid(command,**kwargs):
        Path(command[4]).write_text('not json')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr('app.services.isolated_parser.execute_decoder',invalid)
    with pytest.raises(ResumeParseError) as exc:parse_isolated(path,ResumeParser(),Settings(_env_file=None))
    assert exc.value.code=='parsing_invalid_result'


def test_worker_memory_error_is_not_mislabeled_as_corrupt_file(tmp_path,monkeypatch):
    from app.services import parse_worker
    # Stub resource operations so no limits are ever applied to the pytest process.
    fake=SimpleNamespace(RLIMIT_AS=1,RLIMIT_CPU=2,RLIMIT_FSIZE=3,RLIMIT_CORE=4,setrlimit=lambda *args:None)
    monkeypatch.setitem(sys.modules,'resource',fake)
    monkeypatch.setattr(sys,'argv',['worker','unused.pdf',str(tmp_path/'result.json'),'10485760','52428800','200','384','25','0'])
    def memory(*args):raise MemoryError('PRIVATE-RESUME-TEXT')
    monkeypatch.setattr(ResumeParser,'parsefile',memory)
    assert parse_worker.main()==4
    data=json.loads((tmp_path/'result.diagnostic.json').read_text())
    assert data=={'stage':'decode','outcome':'memory_limit','exception_type':'MemoryError'}


@pytest.mark.parametrize('kind,expected', [('small',200),('complex',200),('invalid',422),('encrypted',422),('scan',200),('docx',200)])
def test_isolated_anonymous_upload_variants(tmp_path,make_pdf,docx_bytes,kind,expected):
    from fastapi.testclient import TestClient
    from app.main import create_app
    content=docx_bytes if kind=='docx' else b'%PDF-1.7\nbroken' if kind=='invalid' else make_pdf(
        ['Name: Alex Example','Skills','Python, React.js']* (80 if kind=='complex' else 1),image=kind=='scan',encrypted=kind=='encrypted')
    if kind=='scan':content=make_pdf(image=True)
    name='resume.docx' if kind=='docx' else 'resume.pdf'
    with TestClient(create_app(Settings(_env_file=None,app_mode='anonymous',isolate_parsing=True))) as client:
        response=client.post('/api/v1/resumes/analyze',files={'file':(name,content)})
        assert response.status_code==expected
        if kind=='scan':assert not response.json()['parsed']['text'] and response.json()['parsed']['warnings']


def test_real_deadline_stops_owned_sleeper(tmp_path,monkeypatch):
    import time
    from app.services.isolated_parser import execute_decoder
    path=tmp_path/'resume.pdf';path.write_bytes(b'%PDF-')
    def sleeper(command,**kwargs):
        return execute_decoder([sys.executable,'-c','import time; time.sleep(30)'],**kwargs)
    monkeypatch.setattr('app.services.isolated_parser.execute_decoder',sleeper)
    started=time.monotonic()
    with pytest.raises(ResumeParseError) as exc:
        parse_isolated(path,ResumeParser(),Settings(_env_file=None,parser_timeout_seconds=1))
    assert exc.value.code=='parsing_timeout' and exc.value.status_code==504
    assert time.monotonic()-started<8
    assert not list(tmp_path.glob('*.json'))


def test_pdf_page_tree_is_traversed_once(tmp_path,make_pdf,monkeypatch):
    from pdfminer.pdfpage import PDFPage
    original=PDFPage.create_pages
    calls=[]
    def pages(document):
        calls.append(1)
        return original(document)
    monkeypatch.setattr(PDFPage,'create_pages',pages)
    path=tmp_path/'resume.pdf';path.write_bytes(make_pdf(['Skills','Python']))
    assert 'Python' in ResumeParser().parsefile(path)['text']
    assert len(calls)==1


def test_repeated_ner_calls_reuse_the_cached_model(monkeypatch):
    from app.services.extraction.ner import load_model
    calls=[]
    fake=SimpleNamespace(pipe_names=['ner'])
    def load(*args,**kwargs):calls.append(1);return fake
    load_model.cache_clear()
    monkeypatch.setattr('spacy.load',load)
    try:
        assert load_model('synthetic-cache-test') is fake
        assert load_model('synthetic-cache-test') is fake
        assert len(calls)==1
    finally:load_model.cache_clear()
