# QA workflow and evidence

## Local Windows PowerShell commands

From the repository root, using the existing virtual environment:

```powershell
backend/.venv/Scripts/python.exe -m pip install --upgrade "pip>=26.2"
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-qa.txt
backend/.venv/Scripts/python.exe -m spacy download en_core_web_sm
npm --prefix frontend ci
Push-Location frontend
node node_modules/@playwright/test/cli.js install chromium
Pop-Location
```

Run backend/API/security regressions and evaluate only the synthetic labeled data:

```powershell
Push-Location backend
.venv/Scripts/python.exe -m pytest -q
Pop-Location
backend/.venv/Scripts/python.exe backend/scripts/evaluate_nlp.py
backend/.venv/Scripts/python.exe backend/scripts/evaluate_matching.py
backend/.venv/Scripts/python.exe backend/scripts/evaluate_relevance.py
backend/.venv/Scripts/python.exe backend/scripts/check_secrets.py
backend/.venv/Scripts/python.exe -m bandit -r backend/app
backend/.venv/Scripts/python.exe -m pip_audit --local --progress-spinner off
backend/.venv/Scripts/python.exe -m pip check
```

Run frontend and real-application checks:

```powershell
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend audit --audit-level=moderate
backend/.venv/Scripts/python.exe backend/scripts/e2e_frontend.py
```

The end-to-end runner creates/stops its own servers and migrated SQLite database.
It never targets your production database. All fixtures and downloaded reports are
synthetic. Browser scans run axe WCAG 2 A/AA and 2.1 AA rules for seven states; JSON
violations/incomplete items and screenshots remain in ignored `.tmp/phase8-e2e-results`.
Keyboard tests check native-dialog focus wrapping, Escape and return focus.

The NLP evaluator creates 20 generated documents in an ignored temporary directory,
calls the original parser and extraction pipeline, and removes the documents. It
records model metadata, dataset SHA-256, TP/FP/FN, distinct-value precision/recall/F1,
section presence, exact field-set success, empty fields and per-case errors in
`docs/evaluation/nlp_results.json` and Markdown. A missing NER model exits nonzero;
it is never reported as a completed NER measurement. Undefined metrics are null,
not fake perfect scores. Tests verify metric arithmetic and strict ranking ties.

Only the generated corpus is CC0-1.0; no license for other project source is implied.
See [annotation scope and corrections](evaluation/annotation-review.md). No real
resume collection, external benchmark downloads, human review or training occurred.

## CI

`.github/workflows/qa.yml` runs on push and pull request with `contents: read`, no
deployment secrets, no privileged pull_request_target execution, disabled persisted
checkout credentials and SHA-pinned official actions.

- Backend: Python 3.11/3.12, real PostgreSQL service, tests, dependency/source/secret
  checks, NLP evaluation and matching diagnostics. The PostgreSQL tests create only
  random temporary schemas/roles. The admin URL is for the disposable CI container;
  a separate privilege probe grants a NOLOGIN role CRUD/USAGE while denying schema
  CREATE, TRUNCATE, superuser, database creation and role creation.
- Frontend: Node 22, lint/format/unit/build/advisory checks, Chromium and real backend
  integration/accessibility tests. The test environment is isolated and synthetic.

The YAML was locally parsed/checked, but this workspace has not been pushed and no
GitHub Actions execution is claimed. CI passing will establish those checks on the
runner, not automatically approve production NLP quality or deployment security.
The generated metrics are diagnostic reports, not a hidden 95% acceptance gate.

For a local PostgreSQL test, configure `TEST_POSTGRES_URL` only for an isolated
test server with temporary-schema/role management privileges; never a production
database. See the existing [backend test instructions](backend-api.md).
The actual deployment should use separate migration and runtime roles, with the
runtime role limited to USAGE and needed SELECT/INSERT/UPDATE/DELETE permissions.
The application must not use the test bootstrap superuser as its deployment role.

## Review boundaries

Advisory scans inspect installed package metadata; the spaCy model distribution is
not on PyPI and is reported as skipped. Model provenance/checksum review and a
hashed deployable lockfile remain release work. Source scanning and the small
secret regex guard supplement manual review; neither proves absence of all flaws.

Document parsing must receive CPU/memory/time quotas and isolation before hostile
internet uploads. Current size/ZIP/page/concurrency limits are useful but do not
constitute a complete sandbox. Review hosting proxy access/error logs to keep
contact information, request bodies, secrets and database parameters out of logs.
No multi-user identity or public candidate history is enabled.

References: [GitHub Python testing](https://docs.github.com/en/actions/tutorials/build-and-test-code/python),
[official setup-python](https://github.com/actions/setup-python),
[official checkout](https://github.com/actions/checkout),
and [axe-core Playwright](https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright).

Read the concise [QA/release decision](qa-report.md) before deployment.
