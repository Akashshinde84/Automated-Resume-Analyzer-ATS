# Anonymous stateless analysis — 2026-11-16

The existing application now opens directly to **AI Resume Analyzer**, with the
subtitle “Upload your resume and get instant AI-powered insights.” There is no
connection modal, login button, access-token input or token state. Selecting or
dropping one valid PDF/DOCX starts analysis automatically. Matching and JSON/PDF
downloads work without an Authorization header.

## Access and data boundaries

`APP_MODE=anonymous` is the new settings/example/Render default and is configured
in the local ignored `backend/.env`. `STORAGE_ENABLED=false` is mandatory in this
mode. The unused local owner-token assignment was removed without displaying it.
The backend refuses an anonymous configuration that enables persistence.

An explicit processing-path allowlist is public: parse-text, extract, legacy match,
integrated analyze, jobs/match and reports. All other v1 operations are denied.
Anonymous requests cannot list, read, delete or save database records, regardless
of whether an old owner Authorization header is supplied. Matching by stored ID,
reporting by stored ID and `store=true` are rejected. The anonymous app never opens
a database connection. Existing private tables/records and backups are not modified.

Legacy `single_user` mode, authenticated ownership checks and DB tests remain for
existing private integrations. The new frontend has no history UI and does not
support that mode. Maintenance of existing records requires a separately controlled
authenticated service or offline administration. Do not publish saved records or
add anonymous persistence without proper session/user authorization.

## Reports without login

The server still signs short-lived, purpose-separated HMAC receipts over complete
analysis/match snapshots. The client keeps them automatically with its current
results in tab memory. A PDF/JSON request must supply its signed analysis and any
match with the exact original resume/job text. Changed, expired or mismatched data
fails. Receipt possession does not provide record lookup or administrative access.
Anonymous and legacy owner receipts use separate signing domains.

`REPORT_SIGNING_KEY` remains a server-only integrity secret, **not a login token**.
Production requires it. Development can generate an ephemeral key automatically;
restart then expires older receipts. No server-side copy of the report/resume is
created by report generation. Downloaded files contain personal data and must be
kept private; clearing the app does not delete copies on the user's device.

## Processing and abuse controls

Input/schema validation, PDF/DOCX signatures, file/request size, DOCX expansion,
PDF page limits, safe generated temporary names, cleanup, private error messages,
and concurrency bounds are retained. Linux decoder subprocess limits and parent
deadlines remain required by production settings. Upload progress is measured;
extraction/skills are shown together because the API does not stream sub-stage
progress. Generating-results status occurs after receiving the actual response.
Failures support explicit retry and cancellation; there is no automatic POST replay.

Public POST requests have configurable sliding-minute limits:

- `ANONYMOUS_REQUESTS_PER_MINUTE=30` per observed network client.
- `ANONYMOUS_GLOBAL_REQUESTS_PER_MINUTE=120` per application process.
- `MAX_CONCURRENT_PROCESSING` bounds simultaneous POST processing independently.

The limiter uses bounded dictionaries/deques and ephemeral salted hashes rather
than raw IP storage. It ignores user-supplied forwarding headers. Invalid requests
also consume a budget, and denied requests are stopped before buffering a body.
429 responses include Retry-After. Reverse proxies/NAT may share a client budget;
do not loosen proxy trust blindly. Counters reset on restart and do not coordinate
replicas. Use a trusted edge/distributed limiter before scaling or making capacity
claims. Resource limits are not a full hostile-code sandbox or antivirus system.

Local CORS remains `http://localhost:5173`; production accepts only explicit HTTPS
frontend origins. CORS is not authentication or a defense against non-browser API
clients. Responses remain no-store; personal content is not added to logs or analytics.

## Changed areas

- Backend settings/security: anonymous mode, exact public allowlist, per-client and
  global rate limits, private-history denial; production guards retained.
- Backend analysis/reports: block repository access and separate anonymous receipt
  signing. Parser/NLP/skills/matching implementations are preserved.
- Frontend Shell/Workspace: remove modal, owner token, connection/history state;
  keep cancellation and in-memory analysis/JD/match state with clear actions.
- Frontend Upload/routes: upload dashboard at `/`, automatic selection/drop analysis,
  responsive guidance, real progress, animated processing and explicit retry.
- Frontend Job/Analysis/Reports/API/Privacy: anonymous requests and current snapshots,
  no save/lookup UI. Unused History/SavedMatches components removed.
- Environment templates, Render, CI, local smoke/browser harness, README and deployment
  guides updated for anonymous operation. Private `.env` remains Git-ignored.

## Executed checks

| Check | Result |
| --- | --- |
| Backend full suite | **263 passed, 3 skipped**, one existing Starlette/httpx deprecation warning |
| Frontend suite | **18 passed**; obsolete saved-history/connection cases replaced with public-flow coverage |
| Real Chromium end-to-end | **4 passed** |
| Axe | **0 violations in 7 states**; 3 incomplete rule results still need manual review |
| Desktop/mobile synthetic screenshots | Reviewed; no login modal or horizontal overflow in tested views |
| Running localhost public smoke | PDF/DOCX/scanned extraction, NER, matching, reports, CORS, private-history denial and invalid files passed |
| Secret guard | 0 findings; ignored personal files/secrets were not scanned or printed |
| Bandit | No medium/high findings; 2 previously reviewed low subprocess warnings remain |
| Render and GitHub CI YAML | Parsed locally; remote execution not claimed |

Backend tests create an actual private saved analysis in an isolated database, then
verify anonymous list/read/delete/match/report/save attempts cannot reach or change
it. Public tests also verify rate limits, invalid uploads, legacy processing routes,
production configuration without an owner token, report tampering and full downloads.
Retained parser, NLP, skill, matching and owner-mode DB/report regressions still pass.

Browser tests cover automatic upload without an Analyze button, real output, optional
matching, interrupted-request retry, both downloads, clear, PDF/scanned/invalid files,
mobile layout, no Authorization header, no persistent browser storage, fresh-browser
isolation, keyboard focus and automated accessibility. No successful response is mocked.

Commands: backend `python -m pytest -q -p no:cacheprovider
--basetemp=../.tmp/anonymous-final-tests`; frontend `npm run lint`,
`npm run format:check`, `npm test`, `npm run build`; root
`python backend/scripts/e2e_frontend.py`, `python backend/scripts/check_secrets.py`,
`python -m bandit -r backend/app -ll`; running local API
`python backend/scripts/production_smoke.py --allow-local` with local URL variables.

The running backend was restarted in anonymous mode; Vite reloads source changes.
Open `http://localhost:5173` and refresh an older tab to reset the former workspace.
No new token or login is needed.

## Limits / not claimed

Three skips are the two unavailable local PostgreSQL checks and the Linux-only
resource probe. The Docker Linux engine is unavailable locally; remote CI/container
and live Render/Vercel smoke tests remain pending. No deployment URL is advertised.
Manual screen-reader/browser/accessibility review and hostile-load benchmarking
remain necessary. Existing OCR, PDF font and weak raw pretrained NER limitations
remain documented in the historical Phase 9 evaluation. No new accuracy, custom
model, sustained public capacity or production-readiness claim is made.
