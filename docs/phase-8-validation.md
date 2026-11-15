# Phase 8 validation — 2026-11-15

## Delivered

- Integrated React/FastAPI flow: health check, upload, text extraction, structured
  candidate parsing, ontology skills, JD input, matching, result presentation,
  authorized history/reopening/deletion and downloadable reports.
- Authenticated `POST /api/v1/reports` with typed JSON/PDF inputs and OpenAPI output
  schemas. Stored reports recheck owner, retention and match parent. Stateless
  reports verify short-lived integrity receipts. Browser access credentials cannot
  forge these receipts; the server uses a separate signing secret.
- JSON reports contain complete current candidate/skill/match information, source
  text, evidence, scores, formulas and suggestions, without credentials/receipts.
- ReportLab PDF reports use embedded fonts, restrained teal/navy styling, A4 pages,
  clear sections, score explanation, matched/missing/preferred skills, provenance
  spans, grounded suggestions, privacy notes and numbered footers.
- Report download retries, cancellation and stale-response protection; preserved
  original JD snapshots; safe ambiguity warnings before retrying failed saves.
- Playwright tests run the real application against generated documents, random
  local ports, a test-only token and a migrated disposable SQLite database.
- Existing parser return contract and database schema remain unchanged. No demo
  scores or synthetic candidate fields are imported into production source flows.

## Changed/created files

| Area | Paths |
| --- | --- |
| Report API/schema | `backend/app/api/reports.py`, `backend/app/schemas/reports.py` |
| Report services | `backend/app/services/report_receipts.py`, `backend/app/services/reports.py` |
| Existing API integration | `backend/app/api/analyses.py`, `backend/app/api/resumes.py`, `backend/app/main.py`, `backend/app/schemas/analysis.py` |
| Ownership/configuration | `backend/app/db/repository.py`, `backend/app/core/config.py`, `backend/.env.example` |
| Runtime dependency | `backend/requirements.txt`, `backend/requirements-dev.txt` (ReportLab moved into runtime requirements) |
| Frontend reports/transport/state | `frontend/src/components/ReportDownloads.jsx`, `frontend/src/lib/api.js`, `frontend/src/context/Workspace.jsx` |
| Frontend integration | `Shell.jsx`, `SavedMatches.jsx`, `pages/Analysis.jsx`, `pages/Match.jsx`, `pages/Job.jsx`, `pages/Upload.jsx`, `pages/Privacy.jsx`, `src/styles.css` |
| Tests | `backend/tests/test_reports.py`, `backend/scripts/e2e_frontend.py`, `frontend/e2e/workflow.spec.js`, `frontend/src/test/reports.test.jsx` |
| Test tooling | `frontend/playwright.config.js`, `frontend/vitest.config.js`, `frontend/package.json`, `frontend/package-lock.json`, `.gitignore` |
| Documentation | `README.md`, `docs/reports.md`, `docs/frontend.md`, `docs/backend-api.md`, `docs/architecture.md`, this validation report |

## Executed commands and outcomes

Commands used the repository root unless a working directory is specified:

| Command | Result |
| --- | --- |
| `npm install -D @playwright/test` (frontend) | Installed; lockfile updated |
| `node node_modules/@playwright/test/cli.js install chromium` (frontend) | Installed isolated Chromium and headless shell |
| `.venv/Scripts/python.exe -m pytest -q --tb=short` (backend) | **229 passed, 1 skipped**, one existing Starlette/httpx deprecation warning |
| `npm test` (frontend) | **20 passed**, 4 test files |
| `npm run lint` (frontend) | Passed, zero errors/warnings |
| `npm run format:check` (frontend) | Passed, including E2E sources |
| `npm run build` (frontend) | Passed: Vite 7.3.8, 53 modules |
| `npm audit --audit-level=moderate` (frontend) | Zero vulnerabilities |
| `backend/.venv/Scripts/python.exe backend/scripts/e2e_frontend.py` | **3 browser tests passed**; full final run 30.2 seconds, process/database teardown succeeded |
| Synthetic API report generation and PDF rendering under `.tmp/` | Passed; all 4 PDF pages rendered and visually inspected |
| `git diff --check` | Passed (workspace remains uncommitted/untracked as in previous phases) |

Final frontend bundle: JS 309.60 kB / 96.88 kB gzip; CSS 30.88 kB / 7.96 kB gzip.
No production chart/icon dependency or paid API was added. ReportLab 4.5.1 was
already available and is now declared as a runtime requirement.

### Backend report coverage

Tests verify JSON/PDF equivalence with actual analysis/matching responses, preserved
Unicode JSON, attachment/no-store headers, absence of receipts/credentials in
downloads, unsigned/tampered candidate/skill/score/job/text rejection, mismatched
analysis/match rejection, owner changes, signing-key changes, expiry, deletion,
authorization, selection of exactly one stored comparison, input-schema errors,
scanned/empty extraction, PDF failures, long text/presentation limits, escaped markup,
body limits and OpenAPI JSON/PDF schemas. Existing parser, Unicode, malformed-file,
NLP, skills, matching, auth, retention and migration tests continue to pass.

### Real-browser coverage

1. **Stateless DOCX:** private connect and health check; upload; real text,
   structured candidate and skill results; analysis-only JSON; pasted JD; interrupted
   matching request and explicit retry; actual score rendering; JD draft changes
   without changing the previous comparison; interrupted report request and retry;
   matching JSON/PDF downloads; exact result equality; disconnect clearing; no
   localStorage/sessionStorage or JavaScript errors.
2. **Saved PDF:** explicit saved analysis and match; private history; reopening
   the selected comparison; saved report scope; canceling deletion and then
   confirming it; empty history after cascade deletion.
3. **Mobile 390px:** home/navigation/upload; no horizontal overflow; scanned PDF
   warnings, missing fields and recovery action. Desktop capture uses 1440px.

The successful requests use real FastAPI responses and the installed pretrained
spaCy baseline. Network interruption is intentionally injected only in tests.
Screenshots/downloads contain generated test data and remain ignored under
`.tmp/phase8-e2e-results/`. The orchestrator never targets a production database.

### Visual checks and fixes

Reviewed captured desktop analysis/match and mobile home/upload/scanned layouts.
The first mobile home screenshot revealed an oversized rotated decorative orbit;
its mobile transform was corrected and an overflow assertion added. Full-page
screenshots now start at scroll position zero so fixed navigation is represented
correctly. A Windows teardown race retaining a temporary database handle was fixed
with bounded retries on the verified disposable directory; the final runner exited 0.

Generated a four-page synthetic report through the real API. Rendered every page
with PDFium 5.15.2 and inspected typography, margins, line wrapping, evidence,
page transitions and footers. No clipping, overlapping elements, unreadable glyphs
or formatting defects were observed. Chromium's PDF viewer also rendered the report.
PDFium was installed only as a local QA tool, not an application dependency.
The renderer download initially stalled; bounded chunk downloads were resumed and
the completed official wheel verified against PyPI's SHA-256 before installation.

## Remaining limits

- Live PostgreSQL integration remains skipped without an isolated PostgreSQL server.
  SQLite migrations/API tests pass; no Phase 8 database migration was needed.
- Python 3.11 remains the target; this machine validated Python 3.12.6 and Node 22.19.
- PDF font coverage is intentionally explicit: unsupported characters become
  `[U+XXXX]` and are explained; complete Unicode remains in JSON. Complex-script/RTL
  typesetting and additional embedded fonts remain unimplemented.
- The PDF is a bounded presentation; large reports show an omission notice and
  refer to complete JSON. Reports are not encrypted; users control downloaded copies.
- Unconfigured signing secrets are per-app and ephemeral. For stable/multi-worker
  stateless receipts, set the same backend-only `REPORT_SIGNING_KEY` on each worker.
  Receipt expiry/restarts/rotation require new analysis/comparison snapshots.
- Chromium desktop/mobile tests do not certify Safari, Firefox, screen readers,
  real devices, deployment origins, TLS, load capacity or provider retention.
- OCR, custom-trained NER, calibrated confidence, semantic embeddings, multi-user
  identity and deployment remain outside scope. No automatic hiring decisions exist.
- ESLint 9 remains pinned for plugin compatibility (npm deprecation noted in
  Phase 7); the final npm advisory audit reports no vulnerabilities.

No real candidate data, credentials or generated reports were committed. No external
database, GitHub repository or hosting resource was provisioned. Phase 8 stops here.
