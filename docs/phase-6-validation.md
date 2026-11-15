# Phase 6 validation

Validated on 2026-11-15 with Windows PowerShell, Python 3.12.6 and Node 22.19.0.
Python 3.11 remains the requested target and is not installed on this machine.

## Results

- Full Phase 1-6 suite: **212 passed, 1 skipped**, final run 10.42 seconds.
- All 178 earlier cases pass in explicitly local legacy test mode; 34 new
  authenticated API/database/security cases pass.
- The one skip is the actual PostgreSQL integration test: TEST_POSTGRES_URL is
  unavailable, and the installed Docker Desktop engine could not start/be reached.
- Real Alembic **upgrade, current, metadata check, downgrade and re-upgrade** ran
  successfully against isolated SQLite databases. Revision: 0001_private_history.
- CLI migration upgrade/current/check passed on a separate ignored local test DB;
  Alembic reported no new upgrade operations.
- PostgreSQL migration SQL compiled successfully with native UUID, JSONB,
  timezone-aware timestamps and cascading foreign keys. Generated SQL is in
  `docs/postgresql-schema.sql`. This is not a live PostgreSQL migration run.
- Real local HTTP smoke check passed and exited successfully after cleanup.
- Frontend production build passed (Vite 7.3.8, 42 modules transformed).
- `pip check`: no broken requirements found.
- Phase 5 diagnostic evaluation remains **10/10 annotated cases passed**.
- One inherited Starlette/HTTPX TestClient deprecation warning remains.

## Live HTTP check

`backend/scripts/smoke_api.py` migrated a throwaway SQLite DB, generated an
unprinted random owner token, started real uvicorn on an ephemeral loopback port,
and exercised synthetic data only:

| Operation | Result |
| --- | --- |
| Public health | 200 |
| Unauthorized history | 401 |
| Analyze and explicitly save | 200 |
| Match and explicitly save | 200 |
| Retrieve detail and list | 200 |
| Delete with cascaded children | 204 |
| Lookup deleted ID | 404 |
| Remaining records | 0 |

The initial HTTP check passed its operations but failed Windows cleanup. The smoke
runner was corrected to stop its own Windows process tree before removing its
throwaway DB. The rerun completed with exit code 0 and no leftover test service.
No production connection or existing user data is used by this script.

## Commands executed

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
Push-Location backend
.venv/Scripts/python.exe -m pytest tests/test_production_api.py -q -p no:cacheprovider
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --tb=short
Pop-Location
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini current
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini check
backend/.venv/Scripts/python.exe backend/scripts/smoke_api.py
backend/.venv/Scripts/python.exe backend/scripts/purge_expired.py
backend/.venv/Scripts/python.exe backend/scripts/evaluate_matching.py
backend/.venv/Scripts/python.exe -m pip check
npm --prefix frontend run build
git status --short
```

CLI migration commands used a process-local DATABASE_URL pointing to an ignored
`.tmp` SQLite file and STORAGE_ENABLED=false; no deployment URL was used. Purge
CLI's disabled-storage path was verified, while actual deletion is tested through
repository/worker tests. SQLite fixtures run real migrations for every isolated DB.

Sandboxed dependency/test attempts hit network or temporary-file permissions;
elevated installation and test execution succeeded. Installed SQLAlchemy 2.0.57,
Alembic 1.20.1, psycopg/psycopg-binary 3.3.9 and dependencies in the existing venv.
No global packages, production secrets, commits, external database provisioning,
public deployment, or multi-user history were created.

## Integration coverage

- End-to-end parser + ontology + typed NLP analysis, then explainable matching.
- Storage off, explicit saving, IDs/TTL and stateless matching without a DB.
- Owner-scoped get/list/delete and prevention of cross-owner ID access.
- Database-level cascades for resume JSON, job text and result evidence.
- Expiry filtering, physical purge, policy shortening and worker startup.
- Pagination for analyses and saved matches; bounded quotas and atomic rollback.
- Authentication before reading bodies, private cache headers and default fail-closed
  behavior on all versioned routes, including legacy endpoints in deployment mode.
- Missing NER fallback, strict model requirement and private inference failures.
- Private DB errors/unforeseen errors with no candidate content in responses/logs.
- Invalid job/UUID/pagination/region/file inputs, body/concurrency limits, OpenAPI
  bearer/multipart documentation, explicit CORS/host restrictions and wildcard rejection.
- Migration/ORM metadata consistency, SQLite upgrade/downgrade, PostgreSQL SQL types.

## Files added or updated

Added database models/session/repository/retention modules, Alembic ini/environment/
revision/template, security middleware/dependency, integrated API router and nested
schemas, API/database tests and optional PostgreSQL test, cleanup/HTTP-smoke scripts,
PostgreSQL SQL artifact, API guide and this report. Updated settings, app lifespan/
composition, upload helper/body route coverage, requirements, environment example,
Git ignores, README, architecture, and explicit local-mode regression fixtures.

## Remaining limits

Live PostgreSQL connectivity, transactions, advisory locks and migrations require
an available test server. Set TEST_POSTGRES_URL to run the isolated random-schema
PostgreSQL test before deployment; SQLite and SQL compilation cannot prove that
runtime behavior. No live PostgreSQL success is claimed.

The deployment has one owner token, not accounts or multi-user authentication.
Retained JSON/text is personal information, not anonymized. Background cleanup
only runs while the service runs; use an external scheduler for at-rest deadlines.
DB row deletion does not erase provider backups/WAL/replicas. Per-process POST
concurrency is not distributed rate limiting or hard parser CPU/memory isolation.
No automatic hosting, dashboard, OCR, or hiring decisions were added.
