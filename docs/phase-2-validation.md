# Phase 2 validation

Validated on 2026-11-15 in Windows PowerShell with Python 3.12.6 and Node 22.19.0.
Python 3.11 remains the requested target but is not installed on this machine.

## Results

- Full backend suite: **44 passed**, including both original health/CORS tests.
- Frontend production build: **passed**, Vite 7.3.8, 42 modules transformed.
- One inherited Starlette/HTTPX TestClient deprecation warning; no failed tests.
- No frontend source changes, deployment, database, OCR, or later-phase features.

Coverage includes PDF and DOCX extraction; all seven canonical sections; alternate,
repeated, and inline headings; Unicode names and normalization; DOCX table order
and header content; blank/zero-byte documents; image-only and mixed PDFs; encrypted
PDFs; malformed PDF, ZIP, and XML; arbitrary ZIP masquerading as DOCX; signature
mismatch; file, request, ZIP expansion, and page limits; missing/wrong/extra form
parts; POST CORS; safe filenames; and temporary cleanup after success and failure.
All document fixtures are synthetic and generated at test time.

## Commands

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
Push-Location backend
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
Pop-Location
npm --prefix frontend run build
backend/.venv/Scripts/python.exe -m pip check
git status --short
git check-ignore --no-index backend/.env frontend/.env uploads/test.pdf sample_resumes/test.docx backend/.venv/Scripts/python.exe frontend/dist/index.html
```

The first dependency installation could not access the package index under the
sandbox; installation succeeded with elevated execution. Tests used elevated
temporary-file access. The frontend build used elevated subprocess access.
`-p no:cacheprovider` avoids the pre-existing sandbox cache-directory limitation.

Added runtime packages: pdfminer.six 20260107, python-docx 1.2.0, python-multipart
0.0.33. ReportLab 4.5.1 is development-only for synthetic PDFs. Existing bounded
requirements remain; no global Python installation was changed.

## Changed files

- Added `backend/app/services/__init__.py` and `parser.py`.
- Added `backend/app/api/resumes.py`.
- Updated app composition, settings, environment example, and requirements.
- Added `tests/conftest.py`, `test_parser.py`, and `test_resumes_api.py`.
- Updated README and architecture; added this report. Phase 1 report is retained.

## Remaining limitations

OCR, semantic candidate/skill extraction, matching, persistence, and upload UI are
not implemented. English heading aliases are heuristic, with unknown headings
retained inside the current section. Complex PDF layouts/font encodings and DOCX
text boxes/revisions may lose ordering or content. Image detection cannot prove
that every textless page is scanned. API processing is for local testing; thread
execution has no hard parser CPU deadline, authentication, or rate limiter. Future
public ingestion requires worker isolation and resource/concurrency controls.
