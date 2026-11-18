# AI Resume Analyzer ? ResumeAtlas

Upload a PDF/DOCX resume, receive structured NLP insights automatically, optionally
compare a job description, and download JSON/PDF reports. No account, login popup
or private access token is needed. The existing React/FastAPI application now uses
**anonymous stateless processing** by default.

**Deployment status:** local application only; no live deployment URLs are verified.
See [deployment settings](docs/DEPLOYMENT.md), [anonymous privacy/security design](docs/anonymous-processing.md)
and [historical NLP evaluation](docs/qa-report.md). Historical phase reports describe
the architecture at that time; the current anonymous guide supersedes token/history instructions.

See the [extraction revision report](docs/extraction-revision.md) for hyperlink/layout fixes, record grouping, measured field-level diagnostics and original-resume validation limits.

## Workflow and features

Open Website ? Upload PDF/DOCX ? Automatic NLP Analysis ? View Results ?
Optional Job Matching ? Download Report.

- Drag-and-drop upload with automatic analysis, real upload progress, animated
  processing, cancellation, validation errors and explicit retry.
- Unicode-preserving PDF/DOCX extraction, section segmentation and alternative headings.
- Name, email, international phone, links, education, experience, projects and
  certification extraction with regex, heuristics and pretrained spaCy PERSON/ORG NER.
- Versioned skill ontology with aliases, categories, contextual rules and source spans.
- Explainable skill coverage and TF-IDF cosine matching, required/preferred gaps
  and evidence-based suggestions. No invented qualifications or hiring decisions.
- Responsive analysis/skills/career dashboard and comparison charts; PDF/JSON downloads.
- No persistent resume history. Temporary uploads are deleted after processing;
  browser results exist only in memory and disappear on clear/reload.
- File signatures, size/expansion/page limits, bounded parsing subprocesses,
  concurrency caps, request rate limits, restricted CORS and signed report snapshots.

Scores are project-defined compatibility estimates, **not ATS scores or hiring
probabilities**. Default weighting is 70% skill coverage / 30% text similarity;
responses show the actual formula and effective weights when signals are absent.

## Architecture and technology

```text
React + Vite + Tailwind + React Router (Vercel)
  ?? HTTPS, no login or Authorization header
     FastAPI + Pydantic (Render, Python 3.11 Docker)
       ?? temporary upload ? isolated pdfminer.six / python-docx decoder
       ?? spaCy + regex/heuristics ? candidate information
       ?? versioned skills ontology ? scikit-learn matching
       ?? signed in-memory snapshots ? ReportLab PDF / JSON
```

`backend/app/` contains API, settings, services, schemas and retained private DB
modules; `frontend/src/` contains reusable components and pages. `backend/tests/`,
`frontend/src/test/` and `frontend/e2e/` cover backend, frontend and real-browser
flows. `docs/` includes architecture/evaluation/deployment guides. Synthetic
resumes are generated during tests; real resumes are never committed.

SQLAlchemy, Alembic and PostgreSQL support remain for legacy owner-only operation
and regression tests. **Anonymous mode refuses storage and never opens the database.**
Saved record endpoints and ID-based matching/report generation return 403, including
when an old owner header is supplied. Existing private database data is untouched.
The public frontend has no history or administration UI.

## Windows PowerShell setup

Install Python 3.11, Node.js 22.12+ and Git. From the repository root:

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install --upgrade pip
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m spacy download en_core_web_sm
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
Set-Location frontend
npm ci
Set-Location ..
```

For an existing installation, preserve your local files instead of copying over
`.env`. Set `APP_MODE=anonymous` and `STORAGE_ENABLED=false` in `backend/.env`.
Remove the unused `SINGLE_USER_API_KEY` from this anonymous service configuration.
Keep `REPORT_SIGNING_KEY` server-only; it is automatic internal report integrity,
not a login credential. Development can leave it blank (restart expires receipts).
Production requires a secure random signing key and isolated Linux parsing.

Start the backend in one terminal:

```powershell
Set-Location "C:\Automated Resume Analyzer & ATS\backend"
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
```

Start the frontend in another terminal:

```powershell
Set-Location "C:\Automated Resume Analyzer & ATS\frontend"
npm run dev
```

Open **http://localhost:5173**. The upload page opens directly. Choose a valid file;
analysis starts immediately. Optionally set a two-letter phone region before upload.
API health: `http://localhost:8000/health`; Swagger: `/docs`; ReDoc: `/redoc`.
No Authorization header is required for public processing endpoints.

Restart the backend after changing backend `.env`. Vite reloads source changes;
restart it after changing frontend environment values. `VITE_API_BASE_URL` is a
public API origin (local default `http://localhost:8000`); never use VITE variables
for secrets or candidate data. CORS locally allows `http://localhost:5173` only.

## API

| Method | Endpoint | Anonymous behavior |
| --- | --- | --- |
| GET | `/health` | Public health check |
| POST | `/api/v1/resumes/analyze` | Multipart PDF/DOCX, candidate/skills/text, `store=false` |
| POST | `/api/v1/jobs/match` | Resume text + job description; no saved analysis ID |
| POST | `/api/v1/reports` | Current signed snapshot, optional bound match; JSON/PDF |
| POST | `/api/v1/resumes/parse-text` | Legacy parser contract, public |
| POST | `/api/v1/resumes/extract` | Legacy structured extraction, public |
| POST | `/api/v1/resumes/match` | Legacy matching, public |
| GET/DELETE | `/api/v1/analyses[/id]` | **403: private history disabled** |

`ResumeParser.parsefile(filepath)` still returns a JSON-serializable dictionary.
Public reports require the exact analysis snapshot and automatically issued report
receipt; altered, expired or mismatched data is rejected. Receipts are kept in tab
memory and are never a user-entered login or a database lookup capability.

## Verification

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests -c backend/pytest.ini
backend/.venv/Scripts/python.exe backend/scripts/check_secrets.py
Set-Location frontend
npm run lint
npm run format:check
npm test
npm run build
node node_modules/@playwright/test/cli.js install chromium
Set-Location ..
backend/.venv/Scripts/python.exe backend/scripts/e2e_frontend.py
```

Backend tests preserve parser/NLP/matching/report coverage and legacy private-history
checks, and add public processing, rate limiting and actual saved-record isolation.
Browser tests verify anonymous automatic DOCX/PDF upload, matching, downloads,
network retry, invalid/scanned files, mobile layout, fresh-browser isolation and axe.
See [QA commands](docs/qa.md) and [evaluation corpus](docs/evaluation/resumes.json).
CI includes Linux production Docker smoke verification; a configured job does not
mean it has run successfully on GitHub.

## Limits and release gates

Scanned/image-only PDFs need future OCR. Complex layouts, ambiguous entities,
multilingual NER and PDF font/shaping remain limited; review extracted data against
the original. No custom NER model was trained. Phase 9's small synthetic corpus had
99.10% canonical-skill F1 but only 22.92% raw PERSON/ORG F1; these are diagnostic
measurements, not real-world accuracy promises. Matching labels are developer-authored.

Default anonymous POST limits are 30/client/minute and 120/service-process/minute;
429 responses include Retry-After. State is bounded and in-process; limits reset
on restart and do not coordinate replicas. Proxy clients can share one budget.
Do not trust arbitrary X-Forwarded-For headers. Add a trusted edge/distributed limiter
before scaling. Isolation limits document decoding, not every NLP/report operation.
Linux container validation, hostile-load capacity, live TLS/CORS and manual broader
accessibility checks remain release gates. PostgreSQL tests are skipped when unavailable;
no DB is required for anonymous use. No live URLs or production readiness are claimed.

## Deployment and screenshots

Use [DEPLOYMENT.md](docs/DEPLOYMENT.md) for Render Docker, Vercel build settings,
server-only secrets, restricted HTTPS origins, smoke checks and rollback.
The server binds `0.0.0.0:$PORT` with one model worker; the public frontend uses
only the configured API URL. The repository includes `render.yaml`, a non-root
Python 3.11 image, production constraints, model-wheel hash and CI checks.

Screenshot placeholders: desktop upload, candidate/skills dashboard, explainable
job match and mobile analysis. Add reviewed fictional screenshots to
`docs/screenshots/`; do not publish personal candidate information.

Keep downloaded reports private. Clearing the application cannot delete copies
already downloaded. Do not commit `.env`, uploads, database dumps or logs. The
synthetic corpus is CC0; no project-wide open-source license has been selected.

## ATS readiness upgrade

Upload a PDF/DOCX to receive an explainable **ATS Readiness Score** without a
job description. The dashboard shows category progress, criterion evidence,
strengths and prioritized improvements. This is a project-defined estimate,
not an official employer ATS score. Academic/personal projects can satisfy the
same description criteria as work experience; social links are optional.

The **Job Match Score** stays separate and uses the existing configurable
skill-overlap and TF-IDF baseline. Project cards show evidenced repository/demo
links; conflicting links remain unresolved. PDF and JSON reports include
readiness, while detailed extraction and rule evidence remain available in JSON.

See [the scoring rubric and configuration](docs/ats-readiness.md) for exact
criteria, limitations, integrity checks and testing instructions. Anonymous
stateless processing, upload limits, decoder isolation and temporary-file cleanup
are preserved. Refresh and reanalyze after updating the backend.
