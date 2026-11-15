# Phase 6: private backend API and optional database

The deployment default is **single-user, authenticated, storage off**. `/health`
is public liveness. Every `/api/v1` endpoint requires a configured bearer token by
default; an unset token fails closed with 503 and a wrong/missing token returns
401. No candidate history is public. No persistent multi-user mode, signup, JWT,
or external identity provider has been implemented or claimed.

## Local setup (Windows PowerShell)

Install dependencies using the existing project virtual environment:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
```

If `backend/.env` does not exist, copy the example **once**. Preserve existing
settings when upgrading an existing environment:

```powershell
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

Generate a private random owner token into the ignored environment file without
printing it. Run this once; rerunning rotates the token and requires all workers
to restart. The `SINGLE_USER_ID` should remain stable across token rotation:

```powershell
backend/.venv/Scripts/python.exe -c "import secrets; from dotenv import set_key; set_key('backend/.env', 'SINGLE_USER_API_KEY', secrets.token_urlsafe(48))"
```

Set/merge these settings in `backend/.env`:

```dotenv
APP_MODE=single_user
SINGLE_USER_ID=primary
STORAGE_ENABLED=false
ALLOWED_HOSTS=["localhost","127.0.0.1"]
CORS_ORIGINS=["http://localhost:5173"]
```

Start the server in one terminal:

```powershell
Set-Location backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal, from the repository root, load the key into a local variable
without displaying it:

```powershell
$apiKey = & backend/.venv/Scripts/python.exe -c "from dotenv import dotenv_values; print(dotenv_values('backend/.env')['SINGLE_USER_API_KEY'])"
$headers = @{ Authorization = "Bearer $apiKey" }
Invoke-RestMethod -Uri 'http://localhost:8000/health'
```

Open http://localhost:8000/docs. Select **Authorize**, then enter the token (the
HTTPBearer control adds the Bearer prefix). The OpenAPI schema documents security,
query parameters, nested JSON schemas, and the multipart upload. Docs/schema expose
no records. Do not put this token in URLs, source files, Git, screenshots, logs,
`VITE_` build variables, or a public frontend bundle. A private UI may accept it in
memory, or a later server-side gateway can hold it; multi-user sharing requires
proper identity and per-user authorization before enabling history for that model.

## Endpoints

| Method / path | Request | Behavior |
| --- | --- | --- |
| GET `/health` | none | Public process liveness; does not claim DB readiness |
| POST `/api/v1/resumes/analyze` | Multipart `file`, optional `phone_region`; query `store=false` | Safe PDF/DOCX parsing, normalized text, sections, skills, candidate/NLP extraction; save only on explicit opt-in |
| POST `/api/v1/jobs/match` | JSON `job_description` and exactly one of `resume` or `analysis_id`; optional weights/store | Existing explainable matcher; saving requires a stored owned analysis ID |
| GET `/api/v1/analyses` | `limit` 1-100, `offset` 0-100000 | Owner-only unexpired summaries, total and pagination; no names, filenames, contacts or resume text in summaries |
| GET `/api/v1/analyses/{analysis_id}` | UUID; `match_limit` 1-50, `match_offset` 0-100000 | Owner-only typed analysis plus paginated saved job/match history and total match count |
| DELETE `/api/v1/analyses/{analysis_id}` | UUID | 204; cascades structured resume, job descriptions, and match results |

Previous `/api/v1/resumes/parse-text`, `/extract`, and `/match` endpoints retain
Phase 1-5 processing contracts, under the same deployment authentication. The new
integrated `/jobs/match` rejects blank job descriptions with 422, while the legacy
matcher preserves its documented null-score behavior for empty descriptions.
Unsupported ontology criteria still give warnings/unavailable scores, not a hiring
judgment. Scoring remains a project-defined estimate, not an ATS score or probability.

For an explicitly local legacy demo only, `APP_MODE=local` with no key allows just
the three legacy processing routes without auth. New integrated and history routes
**still require a token**. Never deploy that local opt-out. Existing unauthenticated
processing tests now explicitly select local mode; security tests use single_user.

### Analyze without saving

PowerShell 7+ supports multipart upload through `-Form`:

```powershell
$analysis = Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/resumes/analyze' -Headers $headers -Form @{ file = Get-Item 'C:/path/to/resume.pdf' }
```

For Windows PowerShell 5.1, use the Swagger UI's **Try it out** upload control
(the shell's `Invoke-RestMethod` lacks `-Form`). The response contains:
`id`, `stored`, `created_at`, `expires_at`, `parsed`, and `extraction`.
Without saving, id/expiry are null and no database is accessed. Raw PDF/DOCX bytes
are only temporary and are deleted before NLP extraction finishes.

### Match without saving

```powershell
$body = @{ resume = $analysis.parsed; job_description = 'Required: Python, SQL; Preferred: Docker' } | ConvertTo-Json -Depth 30
$match = Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/jobs/match' -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

The wrapper has `id`, `analysis_id`, `stored`, and the Phase 5 typed `result`.
Legacy Phase 5 `/resumes/match` still returns its direct result schema.

## PostgreSQL and migrations

Provision a PostgreSQL database and a least-privileged application role outside
this repository. Configure the connection in the ignored backend `.env` or service
environment; use provider TLS settings for remote databases. No credentials are
stored in Alembic configuration, migration files, examples, or source:

```dotenv
DATABASE_URL=postgresql+psycopg://username:URL_ENCODED_PASSWORD@localhost:5432/resume_analyzer
STORAGE_ENABLED=true
```

`postgresql://` and provider-style `postgres://` URLs normalize to the psycopg
SQLAlchemy dialect. SQLite URLs are supported for isolated local tests, not as an
automatic fallback when PostgreSQL fails. URL-encode special password characters.
For a remote deployment, append the provider's appropriate SSL parameters (commonly
`?sslmode=require`). Keep the random API key configured when enabling storage.

From `backend/`, run migrations **before starting database-backed traffic**:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic check
```

Alembic resolves migration paths relative to its ini file and reads DATABASE_URL
from environment/settings. No `create_all()` or destructive reset runs on startup.
Deploy migration execution as a separate release step, then start uvicorn. A failed
or missing database/schema gives private 503 responses for storage operations;
stateless processing stays independent. `/health` remains process liveness.

Tables:

| Table | Purpose |
| --- | --- |
| analyses | UUID, server-defined owner, creation/expiry timestamps and file type; owner/time and expiry indexes |
| structured_resumes | One-to-one FK; parsed text/sections/skills/metadata and typed candidate/NLP JSON |
| job_descriptions | Owned through its parent analysis; job text, creation timestamp |
| match_results | Parent analysis and job FKs; typed scoring/evidence/configuration JSON |

PostgreSQL uses native UUID, JSONB and timezone-aware timestamps. SQLite test
migrations use portable equivalents with foreign keys enabled. Cascades exist in
the database, not only in Python. Transactions roll back partial saves; PostgreSQL
owner quota checks use advisory transaction locks, and match quota checks lock the
parent row. Sessions are never shared between request threads. Engines hide SQL
parameters and do not echo SQL. Server queries filter the configured owner; user
headers/payloads never choose ownership. A mismatched, missing or expired ID gives
the same 404 response.

This is one deployment owner, not multi-user authentication. Do not expose history
to several people with a shared token. Before adding persistent multi-user access,
implement verified identities, user management, ownership assignment from trusted
authentication, and per-user authorization on every operation.

### Save, read, match, delete

With storage enabled, opt in to saving by adding `?store=true` to analyze. To save
a match, send `{"analysis_id":"...","job_description":"...","store":true}`.
Matching an analysis ID without store=true reads it but creates no job/match rows.
Saving a match against stateless supplied resume text is rejected; create a stored
analysis first. Matching never extends the parent's expiry.

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/analyses?limit=20&offset=0' -Headers $headers
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/analyses/$($analysis.id)" -Headers $headers
Invoke-RestMethod -Method Delete -Uri "http://localhost:8000/api/v1/analyses/$($analysis.id)" -Headers $headers
```

Use the id from a **stored** analysis. Storage-disabled history/saving requests give
409 `storage_disabled`. There is no in-memory history fallback or public list.

## Retention and deletion policy

Defaults in `.env.example`:

```dotenv
RETENTION_DAYS=7
RETENTION_CLEANUP_INTERVAL_SECONDS=3600
MAX_STORED_ANALYSES=1000
MAX_MATCHES_PER_ANALYSIS=50
```

Retention is required and bounded to 1-365 days; there is no indefinite-storage
setting. Each saved analysis has an expiry. Reads hide expired rows, with cleanup
on history operations and a periodic startup/background purge. Related PII in
structured data, job descriptions, evidence and matches is deleted by cascading
FKs. Reducing RETENTION_DAYS also shortens effective retention for existing rows;
increasing it does not extend their original expiry. Summary/detail expiry uses
the effective earlier date. Quotas give 409 before saving more history.

Run the same purge from an external scheduler when the web service can sleep or
scale to zero:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/purge_expired.py
```

The CLI prints only an aggregate count, never record contents, URLs or credentials.
The in-process worker cannot physically delete while the app is stopped. Schedule
this command on an always-running trusted host/cron service to enforce at-rest
cleanup deadlines; expired data is never served when the app resumes. Deletion
removes live database rows, not independently managed backups, replicas, exports,
PostgreSQL MVCC/WAL remnants or downstream copies. Configure provider backup
retention/access and deletion procedures separately. Do not claim cryptographic
erasure. No raw upload files are retained by the application.

Disabling storage stops all application history access/writes/cleanup; it does not
delete pre-existing database contents. Purge/delete retained data first or use an
administrative database process if retiring storage. Structured saved data includes
full resume text and candidate PII; it is not anonymized. Restrict database access,
use TLS and provider encryption at rest, and never commit data/backups.

## Request and failure controls

- Explicit CORS origins; Authorization/Content-Type headers; GET/POST/DELETE only;
  credentials disabled. CORS is not authorization.
- ALLOWED_HOSTS is explicit; add your deployed API hostname. Wildcards are rejected.
- Authentication occurs before body buffering or upload processing. Token comparison
  uses constant-time comparison of fixed-length digests; duplicate auth headers fail.
- Per-process MAX_CONCURRENT_PROCESSING (default 2) bounds authenticated POSTs before
  reading bodies; saturation returns 429 with Retry-After. Add ingress rate/body and
  worker CPU/memory limits for an exposed deployment; this is not distributed rate limiting.
- File/request/page/DOCX expansion limits and signature checks from Phase 2 remain.
  Analyze accepts one file and optional validated phone_region. Integrated text is
  capped at 100,000 characters; JSON matching bodies at 2 MiB, JD at 50,000 characters.
- Private responses/errors carry no-store/no-cache and nosniff. Validation responses
  omit Pydantic input/context. Database and unexpected exception contents are not
  returned or sent to server traceback logs. Do not enable third-party SQL/NLP/parser,
  request-body or response debug logging for candidate requests.
- Missing NER gives explicit fallback metadata/warnings by default.
  `REQUIRE_NER_MODEL=true` returns 503 if the model is absent. Unexpected NLP errors
  return 503, never fabricate candidate data, and do not save a partial analysis.
- Malformed uploads return existing clear 400/413/415/422 errors. Invalid JDs return
  422. Database/model outages return private 503. History absence/owner mismatch/
  expiry returns 404. Save quotas/storage-disabled requests return 409.

Use HTTPS at the deployment proxy. The local HTTP examples bind only loopback.
No hosting, external database provisioning, user accounts, OCR, or frontend
credential storage has been configured in this phase.

## Validation and reproduction

```powershell
Push-Location backend
.venv/Scripts/python.exe -m pytest -q
Pop-Location
backend/.venv/Scripts/python.exe backend/scripts/smoke_api.py
```

The full suite applies real Alembic migrations to isolated per-test SQLite files
and tests rollback, FKs/cascades, owner filtering, TTL, auth, limits, and earlier
phase behavior. The smoke script starts real uvicorn on an ephemeral loopback port,
uses synthetic data/random credentials and a throwaway migrated database, checks
all requested endpoints, then stops its own process tree and removes the DB.
It always overrides production DATABASE_URL and never writes production records.

Actual PostgreSQL validation is opt-in using a **test** connection:

```powershell
$env:TEST_POSTGRES_URL = 'postgresql+psycopg://test_user:password@localhost:5432/test_database'
Push-Location backend
.venv/Scripts/python.exe -m pytest tests/test_postgresql.py -q
Pop-Location
```

That test creates a random `ats_test_...` schema, runs migration/API/cascade checks,
and drops only that schema in cleanup. It never selects a production database
implicitly; the role needs schema-creation privileges in the specified test DB.
Do not put test connection secrets into source/CI logs.

In this environment Docker's engine was unavailable despite attempting to start
the installed application. Live PostgreSQL testing is therefore **not verified**;
its migration SQL was generated and checked for native UUID/JSONB/FKs, while actual
upgrade/check/downgrade and all DB API checks ran on SQLite. See
[PostgreSQL SQL](postgresql-schema.sql) and [Phase 6 validation](phase-6-validation.md).
Python 3.11 remains the target; local validation uses the installed Python 3.12.6.

## Phase 8 reports

`POST /api/v1/reports` generates authenticated JSON/PDF attachments from an owned
analysis ID or a signed stateless snapshot, optionally including one comparison.
Integrated analyze/match responses now add nullable `report_token` fields; existing
fields and `ResumeParser.parsefile(filepath)` are unchanged. Receipts are not stored
in database records. No migration is required for Phase 8.

See [report schemas, signing configuration and end-to-end tests](reports.md).
`REPORT_SIGNING_KEY` is server-only and separate from the owner access token. A blank
value generates a per-app key; replicas should share a configured random key.
Reports honor ownership, expiry and deletion and never expose unrelated history.
