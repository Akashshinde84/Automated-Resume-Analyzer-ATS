"""Scan Git-visible source without echoing matched secrets or reading ignored .env.

This conservative guard supplements dependency/source scanners; it is not proof
that no secret exists. Synthetic test tokens and blank .env examples are allowed.
"""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RULES = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "literal_secret": re.compile(r'''(?i)(?:api_key|signing_key|password|access_token)\s*[:=]\s*["']([A-Za-z0-9_+/=-]{32,})["']'''),
}


def main():
    output = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'], cwd=ROOT)
    issues = []
    for relative in set(output.decode('utf-8').split('\0')) - {''}:
        path = ROOT / relative
        if path.is_symlink():
            issues.append((relative, 0, 'source_symlink_requires_review'))
            continue
        if not path.is_file():
            continue
        if path.name.startswith('.env') and not path.name.endswith('.example'):
            issues.append((relative, 0, 'unignored_environment_file'))
            continue
        if path.suffix.lower() in {'.pdf','.docx','.pem','.key','.db','.sqlite','.sqlite3'}:
            issues.append((relative, 0, 'private_or_binary_file'))
            continue
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeError:
            continue
        for name, pattern in RULES.items():
            for match in pattern.finditer(content):
                issues.append((relative, content.count('\n',0,match.start())+1,name))
    for path, line, rule in sorted(issues):
        print(f'{path}:{line}: {rule} (value withheld)')
    print(f'Secret guard: {len(issues)} findings. Ignored environment files and uploads were not read.')
    return bool(issues)


if __name__ == '__main__':
    sys.exit(main())
