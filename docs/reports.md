# Phase 8: authorized reports and integrated workflow

The frontend connects upload, extraction, skills, matching, history, deletion, and
reports through the existing versioned FastAPI APIs. **Check API health** in the
connection dialog calls `/health` without credentials; a private token is still
required to connect and process resumes. No candidate values or scores are mocked
in production. JSON/PDF download buttons appear on the analysis and match pages.

## Download behavior

- **Analysis page:** current analysis, extraction notes, skills, candidate records,
  and evidence. Matching is explicitly absent (`match: null`).
- **Match page:** also includes the displayed comparison, its original job
  description, actual scores, formula, configured/effective weights, required,
  preferred and unspecified skills, missing required skills, evidence, and
  backend-generated suggestions. Editing a JD draft does not change that snapshot.
- **JSON:** UTF-8, schema version `1.0`, complete structured data, source text,
  provenance, warnings and matching result. Credentials and receipts are omitted.
- **PDF:** ReportLab, embedded fonts, A4 pages, consistent hierarchy, evidence
  references, private footer and page numbering. Its presentation is bounded to
  60,000 source characters plus notices. If exceeded, an explicit note points to
  full JSON. Paragraphs wrap and split; external markup/images are escaped,
  never interpreted or fetched.

Reports are generated in memory without saving another server record/file.
Responses use `Cache-Control: no-store` and attachment filenames without candidate
PII. The browser revokes temporary object URLs after starting downloads. Deleting
server records does not delete copies already downloaded to a device.

The PDF embeds ReportLab's bundled Vera fonts. Characters outside their coverage
are displayed as `[U+XXXX]` Unicode codepoints with an explicit font note, rather
than silently dropped or replaced with black squares. JSON preserves original
Unicode. Broader licensed fonts, complex-script typography and right-to-left
shaping remain future work.

## API and authorization

`POST /api/v1/reports` requires bearer authentication and a JSON body. `format` is
`json` or `pdf`. Provide exactly one analysis source and at most one comparison:

| Source | Request fields |
| --- | --- |
| Saved analysis | `analysis_id` |
| Stateless analysis | `snapshot`: unchanged `/resumes/analyze` response |
| Saved comparison | `match_id`, with its owning `analysis_id` |
| Unsaved comparison | `match`: unchanged `/jobs/match` response, plus original `job_description` |
| Analysis only | Omit comparison fields |

A saved report request in JavaScript:

```javascript
const body = { format: 'pdf', analysis_id: currentAnalysis.id, match_id: selectedMatch.id }
```

A stateless comparison request:

```javascript
const body = { format: 'json', snapshot: analysisResponse, match: matchResponse, job_description: originalJobText }
```

The frontend constructs these payloads; users do not need to copy snapshots.
Saved sources are reloaded under the server-defined owner and retention policy.
Matches are selected by both their ID and owned analysis ID. Deleted, expired or
unowned records return 404; old saved snapshots cannot bypass these checks.
Other saved comparisons and history pagination are excluded from the report.

Stateless responses include an opaque `report_token`: an integrity receipt, **not
an access credential**. HMAC-SHA256 binds the exact validated analysis, or matching
result plus resume/original job text, to the owner, bearer credential and expiry.
Signing uses a separate server-only secret; knowing the browser owner token cannot
forge a receipt. Changed content, swapped analyses, malformed/expired receipts,
owner changes or key rotation return a safe 409 instruction to analyze/compare
again. The API does not accept unsigned candidate data or client-generated scores.

Report request bodies are bounded to 4 MiB before JSON parsing. Existing auth,
concurrency, CORS and private-error controls apply. PDF generation errors return
sanitized 503 responses; JSON remains an alternative. `/docs` documents typed
requests and JSON/binary PDF responses.

## Configuration

Existing single-user setup works for one backend process:

```dotenv
REPORT_TOKEN_TTL_SECONDS=3600
REPORT_SIGNING_KEY=
```

TTL accepts 60–86,400 seconds. A blank signing key uses an ephemeral server-only
key generated at startup. Restarting invalidates unsaved receipts; re-upload and
re-compare. Saved reports remain retrievable using their owned IDs.

For multiple workers/replicas or stable receipts across restarts, configure a
shared random backend `REPORT_SIGNING_KEY` of at least 32 characters. Generate it
without printing it, only when intentionally configuring or rotating the secret:

```powershell
backend/.venv/Scripts/python.exe -c "import secrets; from dotenv import set_key; set_key('backend/.env', 'REPORT_SIGNING_KEY', secrets.token_urlsafe(48))"
```

Never put the signing key in the browser, frontend variables, logs or source.
It is separate from `SINGLE_USER_API_KEY`, which the owner enters in the UI.
This remains a single-user deployment; multi-user access is not enabled.

## Retry behavior

POST requests are never automatically replayed. Failed uploads/comparisons retain
inputs for explicit retry. Network failures while saving warn that the request
may have completed and recommend checking history before repeating it. Report
retries are explicit and do not save duplicate records. Auth, expired receipts,
validation and unavailable-model errors remain visible.

Cancel, disconnect and clear abort registered work. A late response cannot start
a report download after clearing the current analysis. Abortion cannot undo server
work already completed. History deletion still requires confirmation.

## End-to-end tests (Windows PowerShell)

From the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
Push-Location frontend
node node_modules/@playwright/test/cli.js install chromium
Pop-Location
backend/.venv/Scripts/python.exe backend/scripts/e2e_frontend.py
```

The orchestrator creates a throwaway migrated SQLite database, generated
PDF/DOCX/scanned fixtures, random test-only token and available local ports. It
starts real Uvicorn/Vite servers, runs Chromium, and stops only its owned process
trees. Existing environment files and external databases are preserved. Temporary
database cleanup retries brief Windows handle locks. Synthetic screenshots and
downloads remain under ignored `.tmp/phase8-e2e-results/`; traces/video are disabled.

Coverage: stateless/saved flows, real extraction/ontology/matching responses, exact
score rendering, both reports, immutable original JD, injected network interruption
and retry, history reopening/deletion, mobile navigation/scanned warnings, browser
storage, JavaScript errors and horizontal overflow. Only network failures are
simulated; successful API responses come from the real backend.

`npm --prefix frontend run test:e2e` can use an already isolated test application
with `E2E_BASE_URL`, `E2E_OWNER_TOKEN`, `E2E_FILES_DIR` and `E2E_OUTPUT_DIR`. Prefer
the orchestrator; never point history/deletion tests at production or real records.

Regular checks:

```powershell
Push-Location backend
.venv/Scripts/python.exe -m pytest -q
Pop-Location
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
```

See [Phase 8 validation](phase-8-validation.md) for results and limitations.
Implementation references: [ReportLab fonts](https://docs.reportlab.com/reportlab/userguide/ch3_fonts/),
[paragraphs](https://docs.reportlab.com/reportlab/userguide/ch6_paragraphs/) and
[Platypus layout](https://docs.reportlab.com/reportlab/userguide/ch5_platypus/).
