# Production deployment: GitHub → Render + Vercel

Status (2026-11-15): configuration prepared; **no live deployment or live URLs verified**.
Account authorization and a successful Linux container CI run are required before release.
The public site supports one private deployment owner. It is not anonymous resume
processing or multi-user SaaS. Keep the bearer token private; never share one token
with unrelated users. PostgreSQL is unnecessary for the initial stateless deployment.

## 1. GitHub authorization and push

This workspace has no remote and originally had no commits. The connected GitHub
account is `Akashshinde84`; its connector cannot create a repository. In GitHub,
sign in, select **New repository**, choose a name (for example
`automated-resume-analyzer`), and create an **empty private repository**. Do not
initialize a README, license or .gitignore. Authorize this repository for Render
and Vercel when each platform asks. Never upload `.env`, resumes or tokens.

Run from the workspace root in PowerShell after reviewing `git status`:

```powershell
git log -1 --oneline
git remote -v
# Replace OWNER/REPOSITORY with the actual newly created empty repository.
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin HEAD:main
```

If `origin` already exists, inspect it and use it only if it is the intended
repository; do not replace it blindly. If the remote contains commits, fetch and
review them before integrating; never force-push. Git Credential Manager may
open interactive GitHub authorization. Do not paste credentials into commands.
Wait for all QA jobs, including `production-container`, to pass on GitHub.
Local Windows tests do not establish Linux production compatibility.

## 2. Reserve the frontend origin

Sign in to [Vercel](https://vercel.com/new), authorize GitHub, and import the repo.
Set **Root Directory: `frontend`**, **Framework Preset: Vite**, **Node.js: 22.x**,
**Install Command: `npm ci`**, **Build Command: `npm run build`**, and
**Output Directory: `dist`**. These commands also live in `frontend/vercel.json`.
Choose the project name and note its actual Production domain from **Settings →
Domains**. It is a configuration value, not proof that the application works.
If a first build is needed to reserve the domain, it will fail safely until the
production API URL is set. Do not work around that guard with an invented URL.

## 3. Render backend

Sign in to [Render](https://dashboard.render.com/), authorize the repository,
then **New → Blueprint**, select the `main` branch and root `render.yaml`.
Review the paid instance selection before creating it. The blueprint selects
`standard` (approximately 2 GB RAM / 1 CPU); this is a conservative starting
budget for spaCy plus a 384 MiB decoder child, not a measured capacity guarantee.

The equivalent manual **New → Web Service** settings are:

| Setting | Value |
| --- | --- |
| Language/runtime | Docker |
| Branch | `main` |
| Root Directory | leave blank |
| Dockerfile Path | `./backend/Dockerfile` |
| Docker Build Context | `./backend` |
| Docker Command | leave blank; image CMD is `python scripts/start.py` |
| Health Check Path | `/health` |
| Auto-Deploy | Off until QA and smoke checks pass |
| Instance | Standard / 2 GB starting budget; verify current dashboard offering |

No shell Build Command is used: Docker installs `requirements-production.txt`,
applies runtime constraints, installs the exact spaCy 3.8.0 model wheel, and loads
it during the build. Python 3.11 is supplied by `python:3.11-slim`. The start
script binds **`0.0.0.0:$PORT`**, defaulting to 8000 outside Render, with one
worker and access logging disabled. Render sets `PORT`; do not pin it to localhost.
The model is warmed at startup; missing model/configuration aborts startup.

Set **Environment** values (JSON arrays must remain valid JSON):

| Variable | Production value / handling |
| --- | --- |
| `DEPLOYMENT_ENVIRONMENT` | `production` |
| `APP_MODE` | `single_user` |
| `SINGLE_USER_API_KEY` | generated secret, at least 32 random characters; owner only |
| `REPORT_SIGNING_KEY` | separate generated secret, at least 32 random characters; server only |
| `CORS_ORIGINS` | JSON array containing only the actual HTTPS Vercel production origin, without a path |
| `ALLOWED_HOSTS` | JSON array containing the actual Render hostname; also any explicitly used API custom hostname |
| `STORAGE_ENABLED` | `false` |
| `DATABASE_URL` | omit while stateless |
| `REQUIRE_NER_MODEL` | `true` |
| `SPACY_MODEL` | `en_core_web_sm` |
| `ISOLATE_PARSING` | `true` |
| `PARSER_TIMEOUT_SECONDS` | `25` |
| `PARSER_MEMORY_MB` | `384` |
| `MAX_CONCURRENT_PROCESSING` | `1` |
| `MAX_UPLOAD_BYTES` | `10485760` (10 MiB) |
| `MAX_DOCX_UNCOMPRESSED_BYTES` | `52428800` (default) |
| `MAX_PDF_PAGES` | `50` |
| `REPORT_TOKEN_TTL_SECONDS` | `3600` (default) |

The blueprint generates both secrets and prompts for origins/hosts. Get the exact
Render hostname from its service dashboard. If it is assigned only after creation,
the initial health check can fail: update `ALLOWED_HOSTS` with that hostname and
redeploy. Do not use `*`. CORS is a browser restriction; bearer authorization is
the access control. Do not authorize arbitrary Vercel preview subdomains.

Model weights download at build time, never during user requests. Runtime pins
are a version snapshot, not a hashed supply-chain lock: NumPy/SciPy use Python
3.11-compatible versions, and container CI must validate the resulting environment.
The model wheel has a SHA-256 pin from the locally installed artifact metadata;
this pins its bytes and is not independent provenance verification.
The base image tag is not digest-pinned. Audit the built image and model artifact
before relying on supply-chain assurances; PyPI auditing skips the model wheel.

## 4. Complete Vercel configuration

In **Project → Settings → Environment Variables**, set for **Production**:

```text
VITE_API_BASE_URL = the actual HTTPS Render API origin (no /api/v1 suffix)
VITE_MAX_UPLOAD_MB = 10
```

These values are public and embedded at build time. Never add `SINGLE_USER_API_KEY`,
`REPORT_SIGNING_KEY` or `DATABASE_URL` under a `VITE_` name. Redeploy after changes.
The production build rejects missing, HTTP, localhost and credential-bearing API
origins. `vercel.json` supplies React Router deep-link rewrites and basic headers.
Once both URLs exist, check that Render `CORS_ORIGINS` exactly matches the browser
origin. Add a custom domain only after validating its TLS and updating CORS/hosts.

## 5. Verification and release gate

Use a fictional resume, never real candidate information for smoke testing.
From PowerShell with backend development dependencies installed:

```powershell
$env:SMOKE_API_URL = Read-Host 'Actual HTTPS API origin'
$env:SMOKE_FRONTEND_ORIGIN = Read-Host 'Actual HTTPS frontend origin'
$privateToken = Read-Host 'Owner API key' -AsSecureString
$env:SMOKE_API_KEY = [System.Net.NetworkCredential]::new('', $privateToken).Password
try {
  backend/.venv/Scripts/python.exe backend/scripts/production_smoke.py
  if ($LASTEXITCODE -ne 0) { throw 'Deployment smoke verification failed' }
} finally {
  Remove-Item Env:SMOKE_API_KEY -ErrorAction SilentlyContinue
  $privateToken = $null
}
```

The script checks HTTPS origins, public health, unauthenticated denial, allowed
and denied CORS, stateless history denial, DOCX/PDF/scanned PDF analysis, actual
NER, matching, signed JSON/PDF reports and malformed/empty/unsupported uploads.
It prints no bearer token or resume/report body and saves no candidate files.
It does not verify frontend rendering, TLS custom-domain provisioning, load
capacity, malware resistance or persistent history.

In the deployed browser, open `/upload` directly and refresh it; connect using
the owner token, upload a synthetic DOCX then PDF, review structured data/skills,
paste a JD, compare, download JSON/PDF, and clear the session. Inspect Network:
all requests must use the intended HTTPS Render origin, no mixed content or
unexpected redirects. Test scanned and invalid files, offline retry, mobile
layout, keyboard traversal and token rejection. Check service metrics for peak
RSS, CPU, processing latency and safe errors. Only then record actual verified
URLs and deployment commit SHA in the release record and README.

## Optional PostgreSQL: defer until history is required

Keep storage off for this release. To enable it later, provision managed PostgreSQL
in the backend region, require the provider's TLS configuration, and store URLs
only as Render secrets. Use a schema-owner migration credential separately from
a non-superuser runtime role with schema USAGE and SELECT/INSERT/UPDATE/DELETE on
the four tables; runtime must not have schema CREATE, table TRUNCATE, CREATEROLE,
CREATEDB or SUPERUSER. Grant sequence usage only if a migration introduces sequences.

With the **migration** URL temporarily provided as `DATABASE_URL`, run from
`backend`: `python -m alembic upgrade head` (Render pre-deploy command on a paid
service, or a controlled one-off shell). Then configure the runtime-only URL,
`STORAGE_ENABLED=true`, `RETENTION_DAYS=7`, and validate all owner-scoped CRUD,
cascade deletion and retention checks against that real database. Avoid putting
the migration credential permanently into the runtime service. Configure managed
backups and test restore/deletion behavior. The automated smoke script deliberately
expects stateless mode; extend its checks before enabling persistence. No production
PostgreSQL grants, TLS, migrations or backups are claimed as verified here.

## Operations, limitations and costs

Linux decoder children enforce address-space, CPU and output-file limits; the
parent kills/waits after the wall-clock deadline and removes temporary files.
This is resource isolation, not a network/filesystem security sandbox. Docker runs
as a non-root user. Validate Linux limits and the built image in CI before release;
Windows tests cover decoding/timeouts but skip Linux-specific limits. API NLP,
matching and reports still run in-process under input/concurrency bounds. Load
and adversarial stress testing remain necessary. Health indicates started API/model
availability in production, not complete per-request or optional DB readiness.

Temporary uploads use ephemeral storage and are deleted after processing. They
are not a backup; restarts erase local files. One worker avoids duplicate model
memory. Scaling requires the same report signing secret across replicas. Rotating
either token or signing secret invalidates existing report receipts; refresh the
owner connection/reanalyze. Logs use fixed error events without text, names, token,
filenames or request bodies; do not enable verbose request/SQL tracing in production.

Plan for cold starts, model warm-up, build download failures, platform request
timeouts, 180-second browser upload timeout, 25-second decoder limit and 429 busy
responses. Do not automatically retry a saved POST. Large/complex PDFs may be
rejected safely. No OCR, multilingual custom NER, antivirus guarantee, multi-user
auth, ATS certification or automatic hiring decision is provided. Extraction is
fallible and requires source review (see the measured Phase 9 report).

Pricing checked 2026-11-15: Render lists the 1 CPU / 2 GB option at about **$25/month**
before workspace, bandwidth, database, taxes or other usage costs; recheck checkout.
Free Render services spin down after 15 idle minutes and are unsuitable as the
validated production target here. Vercel Hobby is for personal non-commercial
use; commercial use requires an appropriate paid plan. No resources have been
purchased by this work. Exact platform timeout/billing limits depend on the chosen
plan; consult the dashboard before launch.

Primary references: [Render pricing](https://render.com/pricing),
[compute plans](https://render.com/docs/compute-plans),
[free limitations](https://render.com/docs/free),
[Blueprint specification](https://render.com/docs/blueprint-spec),
[health checks](https://render.com/docs/health-checks),
[Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite),
[Vercel plans](https://vercel.com/docs/plans/hobby),
[public Vite environment variables](https://vite.dev/guide/env-and-mode).

## Rollback

Keep Render automatic deployment off until approved checks pass; subsequently
prefer `checksPass`. Deploy the last verified commit/image in Render and restore
the corresponding Vercel production deployment if smoke tests fail. Stateless
mode has no database rollback. For future persistence, review migration downgrade
and backup/restore plans separately before changing schemas. Never force-push to
simulate a rollback. No URL should be advertised until verification passes.
