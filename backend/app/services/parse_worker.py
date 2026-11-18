"""Internal decoder entry point with fixed, content-free failure diagnostics."""
import errno
import json
from pathlib import Path
import sys


def diagnostic(destination, stage, outcome, exc=None):
    value={"stage":stage,"outcome":outcome,"exception_type":type(exc).__name__ if exc else None}
    try:
        Path(destination).with_suffix('.diagnostic.json').write_text(json.dumps(value),encoding='utf-8')
    except OSError:
        pass


def main():
    source, destination, upload, expansion, pages, memory, seconds, strict = sys.argv[1:]
    stage='limits'
    try:
        try:
            import resource
        except ImportError:
            if strict == '1':
                diagnostic(destination,stage,'limits_unavailable')
                return 2
        else:
            resource.setrlimit(resource.RLIMIT_AS,(int(memory)*1024**2,)*2)
            resource.setrlimit(resource.RLIMIT_CPU,(max(1,int(seconds)-1),int(seconds)))
            resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024**2,)*2)
            resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        stage='imports'
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from app.services.parser import ResumeParser, ResumeParseError
        stage='decode'
        try:
            result=ResumeParser(int(upload),int(expansion),int(pages)).parsefile(source)
            if len(result['text'])>100_000:
                raise ResumeParseError('extracted_text_limit','Extracted text exceeds the analysis limit.',413)
            envelope={'result':result}
        except ResumeParseError as exc:
            envelope={'error':{'code':exc.code,'message':str(exc),'status':exc.status_code}}
            diagnostic(destination,stage,'document_rejected',exc)
        stage='serialize'
        Path(destination).write_text(json.dumps(envelope,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        return 0
    except MemoryError as exc:
        diagnostic(destination,stage,'memory_limit',exc)
        return 4
    except OSError as exc:
        output_limit=exc.errno==errno.EFBIG
        diagnostic(destination,stage,'output_limit' if output_limit else 'worker_io_failure',exc)
        return 7 if output_limit else 8
    except Exception as exc:
        diagnostic(destination,stage,'initialization_failed' if stage in {'imports','limits'} else 'unexpected_failure',exc)
        return 6 if stage in {'imports','limits'} else 3


if __name__=='__main__':
    raise SystemExit(main())
