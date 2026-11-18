# Deploy anonymous Resume Analyzer: GitHub + Vercel + Render

Current behavior (2026-11-16): no login or owner token. Processing is anonymous,
stateless and does not connect to PostgreSQL. No live URLs or deployment success
have been verified. Follow the release checks before publishing.

## Source control and account handoff

Review `git status`, tests and source secret scanning. Create/select the intended
GitHub repository and authorize Vercel/Render to read it. From the repository root:

```powershell
git remote -v
# Only if no intended origin exists; replace OWNER/REPOSITORY:
git remote add origin https://github.com/OWNER/REPOSITORY.git
git add README.md backend frontend docs render.yaml .github
# Review the staged changes before committing:
git diff --cached --stat
git commit -m "Enable anonymous stateless resume analysis"
git push -u origin HEAD:main
```

Never overwrite an existing remote or force-push. Do not stage actual environment
files, uploaded resumes or databases. The repository ignores them; the secret guard
is an additional check, not proof that secrets cannot exist. Wait for all GitHub
QA jobs including the production-container build/smoke job. Account authorization
must be completed interactively by the owner; no cloud resources were created here.

## Vercel frontend

Import the GitHub repository at https://vercel.com/new. Configure:

| Setting | Value |
| --- | --- |
| Root directory | `frontend` |
| Framework | Vite |
| Node | 22.x |
| Install | `npm ci` |
| Build | `npm run build` |
| Output | `dist` |
| Production `VITE_API_BASE_URL` | Actual HTTPS Render API origin, no `/api/v1` suffix |
| `VITE_MAX_UPLOAD_MB` | `10` |

These settings are also in `frontend/vercel.json`. React Router deep links rewrite
to index.html. The homepage opens the upload dashboard directly. No credentials
belong in frontend variables. Production builds reject missing, HTTP, localhost,
credential-bearing or path-bearing API origins. Environment changes need redeploying.
Reserve/note the actual production domain in Settings ? Domains before configuring
Render CORS. If an initial build fails until the API exists, configure the real URL
and redeploy; do not invent a working URL to bypass validation.

## Render backend

In https://dashboard.render.com choose New ? Blueprint, select the repository,
branch and root `render.yaml`. Review costs before creating the service. Equivalent
manual Web Service settings:

| Setting | Value |
| --- | --- |
| Runtime | Docker |
| Repository root directory | blank |
| Dockerfile | `./backend/Dockerfile` |
| Build context | `./backend` |
| Docker command | blank (image CMD is `python scripts/start.py`) |
| Health check | `/health` |
| Auto-deploy | Off until QA/smoke passes; later prefer checksPass |
| Starting compute budget | Standard / approximately 2 GB and 1 CPU; verify current offering/cost |

Docker supplies Python 3.11, installs production constraints and the hash-pinned
spaCy en_core_web_sm 3.8.0 wheel, verifies it, and runs as a non-root user. The start
script binds **0.0.0.0** and reads the platform **PORT** (fallback 8000 locally),
uses one worker, limits concurrent connections and disables access logs. Model
loading is verified during production startup. No shell build/start override is
needed. Local Docker's Linux engine was unavailable; the Linux build remains a
CI/release gate. Constraints are not a fully hashed lock; audit the actual image.

Set these backend environment variables:

| Variable | Value |
| --- | --- |
| `DEPLOYMENT_ENVIRONMENT` | `production` |
| `APP_MODE` | `anonymous` |
| `STORAGE_ENABLED` | `false` |
| `REPORT_SIGNING_KEY` | Independently generated random secret, at least 32 characters; server only |
| `CORS_ORIGINS` | JSON array containing only the actual HTTPS Vercel production origin |
| `ALLOWED_HOSTS` | JSON array containing actual Render API hostname and any explicitly used custom API hostname |
| `SPACY_MODEL` | `en_core_web_sm` |
| `REQUIRE_NER_MODEL` | `true` |
| `ISOLATE_PARSING` | `true` |
| `PARSER_TIMEOUT_SECONDS` | `25` |
| `PARSER_MEMORY_MB` | `384` |
| `MAX_CONCURRENT_PROCESSING` | `1` |
| `MAX_UPLOAD_BYTES` | `10485760` |
| `MAX_DOCX_UNCOMPRESSED_BYTES` | `52428800` (default) |
| `MAX_PDF_PAGES` | `50` |
| `ANONYMOUS_REQUESTS_PER_MINUTE` | `30` |
| `ANONYMOUS_GLOBAL_REQUESTS_PER_MINUTE` | `120` |
| `REPORT_TOKEN_TTL_SECONDS` | `3600` (default) |

Remove `SINGLE_USER_API_KEY` and `SINGLE_USER_ID` from this public service's settings.
Omit `DATABASE_URL`. They are not needed for anonymous processing. Keep the server
signing key: it protects the integrity of current report snapshots and is never
entered by a user. The Blueprint generates it. To generate independently in a
private local terminal: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Paste the output only into Render's secret field, never Git or VITE variables.

Actual API hostname may be assigned after service creation. Update ALLOWED_HOSTS
with it, then redeploy if the first health check failed. CORS arrays must contain
exact origins without paths or wildcards. Do not allow arbitrary preview domains.
Preview environments should use their own explicitly configured staging backend.
CORS limits browsers; public API clients can still call the API, so it is not abuse
protection or authentication. Configure edge controls as appropriate.

## Database and existing private records

No PostgreSQL service, migrations or persistent disk is required. Anonymous mode
refuses `STORAGE_ENABLED=true`, never initializes a DB, denies all `/analyses`
list/read/delete requests, rejects `store=true`, and rejects stored IDs in matching
or reports. An old owner Authorization header does not grant anonymous-mode access.
Existing database records and backups are left untouched and remain private.

Legacy `APP_MODE=single_user` backend operation still requires an owner secret and
per-owner access checks, for retained integrations/tests. It is not supported by the
new public frontend. If owner data maintenance is necessary, use a separately
controlled authenticated service or offline administration; never enable a public
history UI or share an owner credential across anonymous users. Any future public
persistence requires real session/user authorization before it is enabled.

## Smoke checks

From a development environment with backend dependencies installed:

```powershell
$env:SMOKE_API_URL = Read-Host 'Actual HTTPS API origin'
$env:SMOKE_FRONTEND_ORIGIN = Read-Host 'Actual HTTPS frontend origin'
backend/.venv/Scripts/python.exe backend/scripts/production_smoke.py
if ($LASTEXITCODE -ne 0) { throw 'Smoke verification failed' }
```

No access key is required. This uses generated fictional resumes and checks public
health, anonymous DOCX/PDF/scanned parsing, NER, matching, signed JSON/PDF reports,
invalid uploads, exact-origin CORS and blocked private history. It saves no personal
files or response bodies. It does not prove deployment capacity or frontend rendering.

In the deployed browser, directly open and refresh `/` and `/upload`. Verify no
login modal, select a fictional PDF/DOCX, confirm automatic processing/results,
paste a JD, compare, download both reports, clear the page and reload. Verify mobile
layout, keyboard access, scanned/invalid files, cancellation and network retry.
Inspect Network for HTTPS to the actual API, no Authorization headers, no mixed
content or unexpected redirects. Verify `/api/v1/analyses` returns 403 and a fresh
browser cannot recover another browser's analysis. Test 429 limits using only a
controlled staging service. Record actual deployment URLs and commit SHA only
after all checks pass; none are recorded as live here.

## Privacy, resource limits and operations

Raw uploads/results use temporary files and are cleaned after processing, including
safe failures. No resume storage is enabled. Browser data and automatic report
receipts stay only in tab memory. Signed snapshots expire after one hour by default;
restart with an ephemeral development key or rotate the production signing key and
old receipts stop working. Replicas must share the signing key for consistent reports.
JSON/PDF downloads contain personal data and cannot be deleted by clearing the app.

Linux decoder children enforce memory, CPU and output-file limits, plus a parent
wall timeout. This is resource isolation, not a full filesystem/network sandbox.
NLP/matching/reports still run in-process with input/concurrency bounds. The 2 GB
budget is provisional; measure peak RSS, CPU, latency and failures before launch.
A single model worker avoids memory multiplication. Keep fixed-event error logs;
never enable body/token/resume/SQL value logging. `/health` indicates successful
API/model startup, not a guarantee that all requests or dependencies will succeed.

Rate budgets are bounded in-memory sliding windows per process, using ephemeral
hashed network identities. Do not trust user X-Forwarded-For. Clients behind a proxy
may share a budget. Restarts reset counters; replicas have independent counters.
Add a trusted gateway/distributed rate limiter and validate client-IP forwarding
before scaling or advertising sustained public capacity. Concurrency returns 429
with Retry-After; do not automatically replay POST requests on network failure.

Expect ephemeral storage, cold starts, build/model download failures, platform
request timeouts, the 25-second decoder limit and 180-second browser upload timeout.
Large/complex files may fail safely. Free Render instances spin down after idle
periods and are not the validated production target. Render compute/workspace,
bandwidth and optional database charges are separate; verify current pricing and
billing alerts. Vercel Hobby is for non-commercial personal use; choose a suitable
plan for commercial usage. No resources have been purchased here.

Known functional limits: no OCR, custom-trained NER, multilingual accuracy guarantee,
full PDF complex-script shaping, antivirus guarantee, persistent anonymous history,
independent human relevance labels or hiring decisions. Review the historical QA
metrics and current [anonymous design](anonymous-processing.md). Do not claim
production readiness until Linux CI, load/resource, manual accessibility and live
TLS/CORS/browser smoke gates pass.

## Rollback and references

The readiness upgrade preserves this architecture and needs no database migration.
Configure `READINESS_WEIGHTS` on the backend only if changing the documented
100-point rubric; validate that maxima total 100. See [ATS readiness](ats-readiness.md).
Deploy frontend and backend together and reanalyze open snapshots after the upgrade;
new readiness data is covered by report integrity receipts. Keep `APP_MODE=anonymous`
and production isolation/model requirements. A local build or health check does
not establish successful production deployment. Verify live upload, correct project
links, separate scores, CORS and both report downloads before release.

Deploy the last verified backend image/commit and matching Vercel production
version if checks fail. No DB migration rollback is needed in stateless mode.
Keep auto-deploy off until CI is confirmed; never force-push to roll back.

Official references: [Render Blueprint](https://render.com/docs/blueprint-spec),
[health checks](https://render.com/docs/health-checks), [pricing](https://render.com/pricing),
[free limitations](https://render.com/docs/free),
[Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite),
[Vercel plans](https://vercel.com/docs/plans/hobby),
[Vite environment variables](https://vite.dev/guide/env-and-mode).
