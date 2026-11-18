"""Bounded decoder execution with precise failures and content-free diagnostics."""
import json
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from uuid import uuid4

from app.services.parser import ResumeParseError

MAX_RESULT_BYTES=8*1024*1024
logger=logging.getLogger('app.decoder')
FAILURES={
    2:('parsing_limits_unavailable','Document processing is unavailable because required safety limits could not be enabled.',503),
    3:('parsing_worker_failed','The document processor encountered an unexpected error. Retry Analysis or contact the operator.',500),
    4:('parsing_memory_limit','Document decoding reached its memory limit. Try a simpler text-based PDF or DOCX.',422),
    6:('parsing_initialization_failed','The document processor could not start correctly. Please retry later.',503),
    7:('parsing_output_limit','Extracted document data exceeds the safe output limit.',413),
    8:('parsing_io_failed','Temporary document processing is unavailable. Please retry later.',503),
}


def execute_decoder(command, *, timeout, **kwargs):
    """Own the process tree: Windows venv launchers can have a Python child."""
    kwargs.pop('check', None)
    with subprocess.Popen(command, start_new_session=os.name != 'nt', **kwargs) as process:
        try:
            process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                if os.name == 'nt':
                    try:
                        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=5, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        process.kill()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            process.communicate(timeout=5)
            raise
        return subprocess.CompletedProcess(command, process.returncode)


def parse_isolated(path,parser,settings):
    result_path=Path(path).with_suffix('.result.json')
    diagnostic_path=result_path.with_suffix('.diagnostic.json')
    reference=uuid4().hex[:12]
    started=time.monotonic()
    environment={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP','LANG'}}
    environment.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    command=[sys.executable,'-I',str(Path(__file__).with_name('parse_worker.py')),str(path),str(result_path),
             str(parser.max_size_bytes),str(parser.max_docx_uncompressed_bytes),str(parser.max_pdf_pages),
             str(settings.parser_memory_mb),str(settings.parser_timeout_seconds),
             '1' if settings.deployment_environment=='production' else '0']
    exit_code=None
    def fail(code,message,status):
        diagnostic={}
        try:
            if diagnostic_path.exists() and diagnostic_path.stat().st_size<=4096:
                diagnostic=json.loads(diagnostic_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):
            pass
        def safe(key):
            value=diagnostic.get(key)
            return value if isinstance(value,str) and re.fullmatch(r'[A-Za-z_]{1,64}',value) else 'unavailable'
        logger.warning('decoder_failure reference=%s code=%s exit=%s stage=%s exception_type=%s elapsed_ms=%d',
                       reference,code,exit_code,safe('stage'),safe('exception_type'),int((time.monotonic()-started)*1000))
        error=ResumeParseError(code,message,status)
        error.diagnostic_id=reference
        return error
    try:
        completed=execute_decoder(command,env=environment,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,timeout=settings.parser_timeout_seconds,check=False,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        exit_code=completed.returncode
        if exit_code:
            if exit_code in FAILURES:
                raise fail(*FAILURES[exit_code])
            if exit_code == -getattr(signal,'SIGXCPU',10**6):
                raise fail('parsing_cpu_limit','Document decoding exceeded its CPU time limit. Try a simpler resume.',422)
            raise fail('parsing_worker_terminated','The document processor terminated unexpectedly. Retry Analysis or contact the operator.',503)
        if not result_path.exists():
            raise fail('parsing_result_missing','The document processor returned no result. Please retry or contact the operator.',500)
        if result_path.stat().st_size>MAX_RESULT_BYTES:
            raise fail('parsing_output_limit','Extracted document data exceeds the safe output limit.',413)
        try:
            envelope=json.loads(result_path.read_text(encoding='utf-8'))
            if not isinstance(envelope,dict): raise ValueError()
            if 'error' in envelope:
                error=envelope['error']
                raise fail(error['code'],error['message'],error['status'])
            result=envelope['result']
            if not isinstance(result,dict) or not isinstance(result.get('text'),str): raise ValueError()
            return result
        except ResumeParseError:
            raise
        except (ValueError,KeyError,TypeError):
            raise fail('parsing_invalid_result','The document processor returned an invalid result. Please retry or contact the operator.',500) from None
    except subprocess.TimeoutExpired:
        # The owned decoder tree is stopped and reaped before file cleanup.
        raise fail('parsing_timeout','Document processing timed out. Retry Analysis with a simpler text-based resume.',504) from None
    except ResumeParseError:
        raise
    except OSError:
        raise fail('parsing_unavailable','The document processor could not be launched. Please retry later.',503) from None
    finally:
        result_path.unlink(missing_ok=True)
        diagnostic_path.unlink(missing_ok=True)
