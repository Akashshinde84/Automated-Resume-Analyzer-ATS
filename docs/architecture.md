# Architecture through Phase 8

Phase 1's app factory, API/core boundaries, frontend routing, and settings are
preserved. `backend/app/main.py` composes the health and resume routers, settings,
request-size middleware, and CORS (GET/POST/DELETE; cookie credentials disabled).

- `app/services/parser.py`: `ResumeParser.parsefile(filepath)` returns normalized
  text, canonical sections, warnings, and safe file metadata. Format/input errors
  raise `ResumeParseError`; no API/framework dependency is needed by the parser.
- `app/api/resumes.py`: bounded multipart body, exactly one file, safe temporary
  staging, worker-thread parsing, cleanup, and HTTP error mapping.
- `app/core/config.py`: Pydantic-validated size, expansion, and page limits.
- `tests/`: in-memory/generated synthetic documents, parser and API tests.
- `frontend/`: React/Vite/Tailwind workspace for uploads, candidate analysis,
  explainable matching, and optional authenticated history. See
  [frontend architecture](frontend.md#architecture) for state and transport boundaries.

The body middleware runs inside CORS so size errors receive CORS headers. The
whole body is bounded before Starlette creates multipart spools; the staged file
has a separate size bound. Client filenames never become filesystem paths.
DOCX ZIP members are read in place, not extracted to disk. Expanded byte and
entry counts are checked before parsing. PDF pages preserve layout-derived line
breaks and page boundaries in normalized text. Page numbers for image-only pages
are reported without pretending to have performed OCR.

Section splitting is deterministic heading matching, not NLP. Original normalized
text remains available so callers can recover material missed by segmentation.
Introductory text is heuristically grouped as contact with a warning. Unknown
headings are not semantic boundaries. English aliases are supported; Unicode
candidate text is retained regardless of script.

Phase 6 adds optional database history and single-user authentication. OCR and
deployment remain unimplemented. Phase 5 adds explainable matching.
Phase 3 adds candidate information extraction; Phase 4 adds skill recognition. Parser
threads avoid blocking the async event loop but cannot enforce CPU deadlines;
production processing should use isolated workers and resource quotas.

Targets remain Vercel (frontend, SPA rewrite) and Render (API). No hosting changes
are performed. Health remains process liveness, not database readiness.

API references used: https://pdfminersix.readthedocs.io/en/latest/reference/highlevel.html
and https://python-docx.readthedocs.io/en/latest/api/document.html.


## Phase 3 boundaries

- `app/schemas/candidate.py`: typed nested extraction contracts and input limits.
- `app/services/extraction/`: orchestrator plus isolated contacts, dates, identity,
  section-record, and pretrained spaCy adapter modules.
- `app/api/extraction.py`: JSON `/api/v1/resumes/extract` endpoint using worker
  execution; it consumes Phase 2 text without changing the parser contract.
- `app/main.py`: validation errors omit sensitive input/context; the existing
  bounded-body middleware also limits the new JSON endpoint before decoding.

The NLP adapter lazily caches the installed official model and serializes shared
inference. Missing models explicitly report unavailability rather than silently
claiming pretrained results. Rules work independently and never train a model.
Baseline PERSON/ORG spans remain separate from section-local field assignments.
Phone-region context is caller-supplied; there is no inferred default country.
Schemas retain nulls, raw source blocks, provenance, and review warnings. No
resume bodies or inference exception details are logged. See `nlp-extraction.md`
for method differences, supported patterns, and limits.


## Phase 4 boundaries

- `app/data/skills.json`: local semantic-versioned ontology, reviewed as source.
- `app/schemas/skills.py`: strict ontology validation and typed skill occurrences.
- `app/services/skills.py`: escaped alias matching, Unicode boundaries, context
  gates, longest-phrase handling, and canonical deduplication with all occurrences.
- `app/services/sections.py`: shared heading vocabulary and offset-preserving
  iteration, so repeated sections do not lose provenance positions.
- `ResumeParser`: adds skill results and ontology version after text normalization.

The default matcher caches only compiled configuration. Per-resume results stay
local to each call. Skills do not depend on the pretrained model, network calls,
or Phase 3 candidate inference. Parser fields remain compatible with additive
skill fields; the `/extract` schema is unchanged. Details: `skills.md`.


## Phase 5 boundaries

- `app/schemas/matching.py`: bounded parsed-text input, configurable validated
  weights, typed scores, job-skill classifications, evidence and suggestions.
- `app/services/matching/safety.py`: professional resume sections and shared
  personal/instruction/negation gates; no inference from personal attributes.
- `app/services/matching/job.py`: required/preferred/unspecified clause rules.
- `app/services/matching/text.py`: consistent allowlisted canonical skill/task
  representation, pair-local binary TF-IDF and cosine contributions.
- `app/services/matching/__init__.py`: coverage, weighting and evidence-grounded
  suggestions, with no hiring thresholds or predictor training.
- `app/api/matching.py`: `/api/v1/resumes/match`, thread execution and private errors.
- Settings/environment: default weights; bounded-body middleware covers matching
  JSON before decoding. Parser and candidate extraction contracts are preserved.

Only resume text is read from parsed input; skills and evidence are re-extracted
with the existing ontology. No raw personal vocabulary reaches TF-IDF. Task words
require local accepted skill evidence. No candidate results, vectors or IDF are
cached across requests. The synthetic evaluation script uses annotated diagnostic
pairs, not hiring outcomes. See `matching.md` for formulas and honest limits.


## Phase 6 boundaries

- `app/core/security.py`: fail-closed single-owner bearer access before body reads,
  private cache headers, concurrency bounds and sanitized unforeseen errors.
- `app/api/analyses.py`: integrated typed analysis/jobs/history APIs, explicit saving.
- `app/schemas/analysis.py`: parsed resume, analysis, history and job-match contracts.
- `app/db/models.py`: parent ownership/expiry and three child tables using JSONB on
  PostgreSQL, portable JSON for test SQLite. Database cascades enforce deletion.
- `app/db/repository.py`: operation-local sessions/transactions, owner filtering,
  TTL gates, bounded pagination, atomic writes and quotas.
- `app/db/retention.py`: startup/periodic expiry purge; external purge CLI supports
  cleanup while web instances sleep. No raw files are stored.
- `alembic/`: explicit migrations; no table creation/reset during app startup.

Deployment defaults are authenticated and stateless. No multi-user principal or
public history endpoint exists. Only a server-configured owner scope is used; a
future multi-user implementation must bind ownership to verified authentication
and authorization. Prior unauthenticated processing is confined to an explicit
local legacy opt-out, and never applies to new integrated/history endpoints.

App lifespan owns/disposes the optional engine and retention worker. APIs perform
CPU/database work in worker threads, with sessions never shared across operations.
Missing models warn or fail under strict configuration; storage failures roll back
and return private errors. JSON/body/upload limits and explicit CORS/hosts apply.
See `backend-api.md` for endpoint schemas, exact setup, privacy and honest runtime
validation limits. Production PostgreSQL is supported but live validation needs an
available server; SQLite integration and PostgreSQL SQL compilation are separate.

## Phase 8 boundaries

- `app/schemas/reports.py`: mutually exclusive owned-ID/signed-snapshot inputs and
  versioned JSON report schema.
- `app/services/report_receipts.py`: expiring owner-bound receipts with a private
  signing key separate from the browser owner token.
- `app/api/reports.py`: rechecks ownership/retention or integrity, selects one
  comparison, and generates private JSON/PDF attachments in memory.
- `app/services/reports.py`: bounded ReportLab presentation, embedded fonts,
  escaped text, explicit font/presentation limits, and no external resources.
- Frontend report controls preserve the original compared JD, abort stale downloads,
  and offer explicit retries without automatically replaying POSTs.
- `frontend/e2e/` and `backend/scripts/e2e_frontend.py`: Chromium + React + FastAPI
  tests with generated fixtures and a disposable migrated database.

The existing `ResumeParser.parsefile(filepath)` contract and DB tables are unchanged.
Receipts are additive API fields, not stored DB fields. JavaScript/Pydantic
compatibility is verified through real payloads, OpenAPI, and integrated tests.
