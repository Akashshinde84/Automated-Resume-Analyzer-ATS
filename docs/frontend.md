> Current default: anonymous stateless processing, no login, no persistent history. See [anonymous design](anonymous-processing.md) and [current deployment guide](DEPLOYMENT.md). Owner-token and saved-history instructions below describe the retained legacy single_user backend, not the public frontend.

# Frontend through Phase 8

Resume Atlas is the React frontend for the Automated Resume Analyzer. All candidate
information, detected skills, scores, evidence, and improvement suggestions come
from FastAPI. The landing illustration explains the workflow; it contains no
sample candidate or score. No chart dependency is needed for the accessible CSS
score ring.

## Local setup in Windows PowerShell

Use Node.js 22.12+ and the backend environment from the
[backend guide](backend-api.md). From the repository root:

```powershell
if (-not (Test-Path frontend/.env)) { Copy-Item frontend/.env.example frontend/.env }
npm --prefix frontend ci
npm --prefix frontend run dev
```

The frontend runs at **http://localhost:5173**. In another terminal:

```powershell
Set-Location backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend must have a random `SINGLE_USER_API_KEY` configured. Follow the
[backend token setup](backend-api.md#local-setup-windows-powershell), then restart
the API. Use **Connect backend** in the frontend and enter the existing token
from your ignored backend environment file. Do not paste it into source files,
screenshots, URLs, frontend environment variables, or Git. No authentication
credentials are bundled, logged, or stored in localStorage/sessionStorage.

Frontend public configuration:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
VITE_MAX_UPLOAD_MB=10
```

Restart Vite after changing configuration. The size setting is only a client-side
hint; backend validation of size, type, signature, and document content remains
authoritative. Keep it aligned with `MAX_UPLOAD_BYTES`. The API URL should point
to the intended trusted backend. Use HTTPS for deployed origins. `VITE_` values
are public build-time values; **never add a private token to them**.

Configure backend `CORS_ORIGINS=["http://localhost:5173"]`. If using a different
host or preview port, add its exact origin explicitly and restart the API.
Production preview defaults to http://localhost:4173 and needs its own CORS origin.

## Pages and workflow

| Route | Behavior |
| --- | --- |
| `/` | Application overview and workflow explanation |
| `/upload` | Browse or drop one PDF/DOCX; optional phone region and explicit saving |
| `/analysis` | Candidate details, skills, education, work, projects, certifications, warnings, and source evidence |
| `/job` | Paste up to 50,000 characters; compare with the current analyzed resume |
| `/match` | Real component/overall scores, backend formula/weights, skill comparisons, and grounded suggestions |
| `/history` | Authenticated saved analyses, paginated loading, and confirmed deletion |
| `/privacy` | Processing, memory, optional persistence, deletion, and extraction/scoring limits |

1. Connect the private owner session. Connection checks authenticated history;
   `409 storage_disabled` means an authenticated **stateless** session, not failure.
   Other failures remain visible and do not establish a session.
2. Upload a readable resume. Actual byte-transfer progress is displayed; after
   upload, an indeterminate processing state is shown. The backend does not expose
   separate stage progress. Cancel aborts the request; it cannot guarantee that
   server processing has not already completed. Check history if saving was enabled.
3. Review results. Unknown fields remain “Not identified”; missing scores remain
   “Not available.” Warnings explain image-only PDFs and missing NER models. Empty
   extracted text blocks the job comparison flow and offers another upload. OCR
   remains unimplemented.
4. Paste the job description and compare. A saved analysis uses its ID; a stateless
   analysis sends only its parsed text. Server-configured scoring weights remain
   authoritative and are explained in the results. TF-IDF is lexical similarity,
   not semantic embeddings. Suggestions are never invented by the frontend.
5. If storage is enabled, explicitly opt in to saving. Reopen saved comparisons
   from a saved analysis. Delete through history; confirmation defaults to the
   non-destructive choice. Deleting an analysis cascades its jobs and matches.

## Privacy and persistence

This remains a **single-user owner workspace**. It does not implement multi-user
identity or invite/sharing flows. History appears in navigation only after a
successful authenticated persistence check. A manually entered `/history` route
still shows an honest unavailable state when storage is disabled.

Tokens, current analysis, job text, and match results live only in React memory.
Disconnect aborts registered work and clears these values; reload starts a fresh
session. Clearing memory does not delete saved server records. Saving an analysis
and saving a comparison each require an explicit checkbox. Retention is controlled
by backend settings; history shows server-provided expiration dates. Upload files
are not retained by the backend. No analytics, external fonts, paid AI API, or
client-side content logging was introduced. Deployment providers and database
backups have separate policies that the operator must review.

## Architecture

- `src/context/Workspace.jsx`: private session, capability discovery, current
  analysis/JD/match, request cancellation, and reset on disconnect.
- `src/lib/api.js`: bearer-authenticated fetch/XHR, secure backend error mapping,
  client file checks, safe external links, and null-aware score formatting.
- `src/components/`: responsive navigation, native modal dialogs, errors, warnings,
  skeletons, empty states, evidence details, error boundary, and saved comparisons.
- `src/pages/`: route-specific presentation and operations. No results are generated
  or scored in the browser.
- `src/styles.css`: Tailwind entry, reusable design tokens/styles, mobile layouts,
  visible focus, readable contrast, and reduced-motion behavior.
- `src/test/`: mocked transport and React integration tests using synthetic data.

React escapes document strings; no raw HTML rendering is used. External links are
limited to HTTP(S) without embedded credentials and opened with `noopener` and
`noreferrer`. API fetches omit cookies, disable caching, and reject redirects.
Upload uses XHR for genuine progress and a three-minute timeout. Results remain
subject to backend parser and model limitations. Request abortion is best effort.

Navigation supports a skip link, route heading focus, keyboard controls, accessible
labels, native dialog focus containment, live loading/error announcements, and
reduced motion. Layout breakpoints cover mobile, tablet, and desktop. An error
boundary offers a reload into a fresh session without printing sensitive content.

## Verification and hosting preparation

```powershell
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run format:check
npm --prefix frontend run build
npm --prefix frontend run preview
```

Scripts invoke Node entry points directly, avoiding Windows command shim problems
in workspace paths containing `&`. `npm run format` formats source/configuration.
The frontend lockfile pins the validated dependency graph. ESLint includes React
Hooks and JSX accessibility rules. Vitest/JSDOM tests exercise synthetic workflow
responses; they are not real browser visual or assistive-technology certification.

`frontend/vercel.json` supplies an SPA fallback for direct route navigation and
basic response headers. No site was deployed. A future deployment must configure
the public API URL, HTTPS, exact backend CORS/allowed hosts, secrets exclusively
on the backend, and the backend retention worker. Secure multi-user access requires
identity and per-user authorization before sharing persistent history.

Manual review still recommended: desktop/mobile rendering, real file picker and
drag/drop, keyboard and screen-reader navigation, browser password-manager policy,
large documents, slow connections, CORS errors, and your deployed API origin.

Phase 8 adds authorized JSON/PDF downloads, a public health check in the connection
dialog, original-JD snapshots, safe report retry/cancellation, and Chromium end-to-end
tests. See [reports and integrated workflow](reports.md). Captured layouts cover
desktop analysis/results and mobile home/upload/scanned states. Full assistive
technology and deployed-origin testing remain manual.
