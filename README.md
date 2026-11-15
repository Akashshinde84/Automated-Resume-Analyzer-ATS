# Automated Resume Analyzer ? ResumeAtlas

A React dashboard and FastAPI service for extracting candidate information from
PDF/DOCX resumes, recognizing skills and explaining compatibility with a pasted
job description. Every displayed result comes from the backend.

**Release status:** Phase 10 deployment configuration is prepared; deployment and
live smoke tests are pending. **No verified live URLs are available.** This is a
single-owner application with a public website and private authenticated analysis.
It is not a multi-user job portal. See [deployment instructions](docs/DEPLOYMENT.md)
and the [release validation record](docs/phase-10-validation.md).

## Features

- PDF and DOCX text extraction, Unicode normalization and section detection.
- Regex, explicit heuristics and pretrained spaCy NER for candidate details,
  contacts, education, work experience, projects and certifications.
- Versioned skill ontology with aliases, contextual matching and source evidence.
- Required/preferred skill comparison and explainable TF-IDF cosine similarity.
- Responsive upload, analysis, job comparison, privacy and report screens.
- Signed, authorized JSON and PDF report downloads; safe error/retry states.
- Optional owner-scoped PostgreSQL history and deletion; storage is off by default.
- Bounded uploads, safe temporary files, exact-origin CORS, bearer authorization,
  production configuration guards and isolated Linux document decoding.

The default overall score combines 70% skill overlap and 30% text similarity;
missing signals change the effective weights as documented in the response.
It is a project-defined compatibility estimate, **not an ATS score, hiring
probability or automatic hiring/rejection recommendation**. No qualifications
are invented; missing fields remain empty and skill mentions do not prove ability.

## Architecture and stack

```text
Browser / React + Vite + Tailwind + React Router (Vercel)
    ? HTTPS + owner's in-memory bearer token
FastAPI + Pydantic (Render, Python 3.11 Docker)
    ??? bounded temporary upload ? isolated PDF/DOCX decoder
    ??? regex + heuristics + pretrained spaCy PERSON/ORG baseline
    ??? versioned skill ontology ? scikit-learn matching
    ??? signed JSON / ReportLab PDF reports
    ??? optional SQLAlchemy ? PostgreSQL; Alembic migrations
```

```text
backend/app/       API, settings, schemas, services, ontology and database modules
backend/tests/     Unit, API, privacy/security and deployment tests
backend/scripts/   Evaluation, QA, production start and smoke verification
frontend/src/      Pages, reusable components, API client and memory-only state
frontend/e2e/      Playwright workflows against the real local backend
docs/              Architecture, API, evaluation, QA and deployment guides
sample_resumes/    Instructions; fictional fixtures are generated, not committed
.github/workflows/ CI tests, audits, builds, browser and production-container checks
render.yaml        Stateless authenticated Render deployment blueprint
```

Runtime libraries include pdfminer.six, python-docx, spaCy, phonenumbers,
scikit-learn, SQLAlchemy, Alembic and ReportLab. Tests use pytest, Vitest,
Testing Library, Playwright and axe. No external paid NLP API is used.

## Windows PowerShell setup

Install Python 3.11, Node.js 22.12+ and Git. From the repository root:

```powershell
py -3.11 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install --upgrade pip
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m spacy download en_core_web_sm
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
```

Generate two independent random secrets locally, then put one in
`backend/.env` as `SINGLE_USER_API_KEY` and the other as `REPORT_SIGNING_KEY`:

```powershell
backend/.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Run that command twice. Keep both outputs private. Only the owner API key is
entered in the dashboard connection dialog; never give the signing key to the
browser. `.env` files, virtual environments, uploads, resumes and generated
reports are ignored by Git. Do not put private values in `VITE_` variables.

Start the backend in one PowerShell terminal:

```powershell
Set-Location backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
```

In another terminal from the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://localhost:5173`, connect with the owner API key, and upload a PDF or
DOCX. The API runs at `http://localhost:8000`; Swagger UI is `/docs`, ReDoc is
`/redoc`, and OpenAPI JSON is `/openapi.json`. Use **Authorize** with the bearer
key for protected requests. Default CORS permits `http://localhost:5173`; if you
change the browser origin, update `backend/.env` and restart the API.

## API

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health` | Public startup/liveness check |
| POST | `/api/v1/resumes/analyze` | Multipart PDF/DOCX, text + candidate + skills |
| POST | `/api/v1/jobs/match` | Parsed resume text or owned analysis ID + job text |
| POST | `/api/v1/reports` | Signed current analysis, optional matching, JSON/PDF |
| GET | `/api/v1/analyses` | Owner history, only when persistence is enabled |
| GET | `/api/v1/analyses/{id}` | One unexpired owned record |
| DELETE | `/api/v1/analyses/{id}` | Delete analysis and related records |

All `/api/v1` endpoints require bearer authorization in the default mode.
Earlier parse-text/extract/match APIs and `ResumeParser.parsefile(filepath)`
remain supported. The parser returns a JSON-serializable dictionary.
See [API contracts](docs/backend-api.md), [report security](docs/reports.md),
[matching formula](docs/matching.md) and [ontology maintenance](docs/skills.md).

## Verification

From the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests -c backend/pytest.ini
backend/.venv/Scripts/python.exe backend/scripts/check_secrets.py
backend/.venv/Scripts/python.exe backend/scripts/evaluate_nlp.py
backend/.venv/Scripts/python.exe backend/scripts/evaluate_matching.py
backend/.venv/Scripts/python.exe backend/scripts/evaluate_relevance.py
Set-Location frontend
npm run lint
npm run format:check
npm test
npm run build
node node_modules/@playwright/test/cli.js install chromium
Set-Location ..
backend/.venv/Scripts/python.exe backend/scripts/e2e_frontend.py
```

See [QA commands](docs/qa.md) for dependency/security checks and PostgreSQL test
setup. CI covers Python 3.11/3.12 and disposable PostgreSQL. A production Docker
job builds the image and exercises generated DOCX/PDF, NER, matching and reports.
A configured job is not evidence of a successful remote run.

## Evaluation and limitations

The [Phase 9 QA report](docs/qa-report.md) records 20 fictional labeled profiles
(10 PDF + 10 DOCX), measurement definitions and annotation corrections. Canonical
skill F1 was 99.10% on this small, explicit synthetic corpus; raw pretrained
PERSON/ORG F1 was only 22.92%. These are diagnostic measurements, not general
accuracy guarantees. Matching relevance labels are developer-authored; no
independent human relevance evaluation or custom NER training is claimed.

- Scanned/image-only PDFs return warnings; OCR is not implemented.
- Complex layouts, ambiguous entities, non-English NER and incomplete records
  require source review. Degree detection uses heuristics, not an assumed NER label.
- PDF reports have font/shaping limits; JSON preserves Unicode information.
- The first deployment is stateless and one owner only. No public candidate
  history, signup, password reset or per-user accounts are implemented.
- Linux CPU/memory limits need successful container CI validation; host load,
  resource-exhaustion testing and manual accessibility review remain pending.
- Production PostgreSQL permissions, TLS, backups and migrations are unverified
  and are unnecessary while storage stays disabled.
- Runtime versions and the model wheel hash are pinned, but the full dependency
  graph and base image are not hash-locked. Dependency scans do not prove a system free from vulnerabilities.

## Deployment

Use [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for exact GitHub push, Render Docker,
Vercel root/build settings, secrets, CORS, optional migrations, costs, rollback
and live smoke checks. The backend starts with `python scripts/start.py`, binds
`0.0.0.0` and reads `PORT`. The frontend uses the public build-time
`VITE_API_BASE_URL`. HTTPS and exact production origins are required.

| Deployment | Verified URL |
| --- | --- |
| Frontend / Vercel | Pending account authorization and live verification |
| Backend / Render | Pending account authorization and live verification |
| GitHub repository | No remote configured yet |

## Screenshots

Place reviewed screenshots with fictional data under `docs/screenshots/` after
validation. Placeholders: desktop analysis dashboard, job match explanation,
mobile upload, and privacy/deletion information. No screenshots or live results
are fabricated here.

## Privacy and contribution

Resume data contains personal information. Review downloaded reports privately;
deleting server records cannot delete downloaded copies. Do not commit real
resumes, logs, database dumps or credentials. The default keeps token/results
only in browser memory and raw uploads only in temporary server files. Review
[security findings](docs/security-review.md) before changing access or storage.
The synthetic evaluation corpus is explicitly CC0; that does not license the
whole application. No project-wide open-source license has been selected.
