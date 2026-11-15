# Phase 10 deployment preparation — 2026-11-15

**Status: prepared locally; not deployed or declared production-ready.** No live
URLs are verified. The account handoff and exact settings are in
[DEPLOYMENT.md](DEPLOYMENT.md). No unrelated repository was changed, no remote
was overwritten and no cloud resources were purchased.

## Delivered

- Render Docker blueprint, Python 3.11 non-root image, allowlisted build context,
  runtime version constraints and hash-pinned spaCy 3.8.0 model wheel.
- Production start script binds `0.0.0.0` and platform `PORT`, one worker, no
  request access log. Fixed unexpected-error events contain no request content.
- Production settings require private bearer/report secrets, exact HTTPS CORS,
  required NER and Linux isolated parsing; missing model aborts startup.
- Decoder child receives no API/database secrets, has Linux address-space/CPU/
  output-file limits and a parent-enforced 25-second wall timeout. Temporary
  uploads/results are cleaned. Direct `ResumeParser.parsefile` remains intact.
- Vercel Vite install/build/output settings, deep-link routing and production
  API-origin validation. Only public URL/size variables belong in frontend env.
- Stateless synthetic smoke script for health, CORS/auth, parsing/NER/matching,
  signed JSON/PDF reports and invalid uploads; production Docker CI job added.
- Professional README, account/push instructions, optional PostgreSQL migration/
  runtime role guidance, costs, limitations, rollback and verification steps.

## Audit

Before final documentation, 151 Git-visible files totaled 920,550 bytes; none
exceeded 1 MiB. Source secret guard found **0 findings**. Uploaded resumes,
environment files, databases, virtual environments, node_modules, `.tmp`, caches,
generated reports and build outputs are excluded from Git. Ignored private files
were not read or removed. No actual resume file is committed; evaluation fixtures
are generated from fictional source text. Subsequent additions are text docs/config.

## Executed validation

| Check | Result |
| --- | --- |
| Full backend pytest | **249 passed, 3 skipped**, one existing Starlette/httpx deprecation warning |
| Deployment-specific tests | 6 passed; Linux CPU/memory probe skipped on Windows |
| Frontend unit/integration tests | **20 passed** |
| Real Chromium primary workflows | **4 passed**, including report retry, history deletion, mobile/scanned and keyboard/axe states |
| Local start script + isolated parser smoke | Passed: actual PDF/DOCX/scanned analysis, NER, matching, authorized JSON/PDF reports, invalid uploads, auth and CORS |
| Frontend lint / format / production build | Passed; 53 modules, JS 310.07 kB (97.05 kB gzip), CSS 31.10 kB (8.01 kB gzip) |
| npm audit | 0 reported vulnerabilities |
| Installed Python pip-audit | No known advisories for auditable packages; en-core-web-sm skipped by PyPI audit |
| `pip check` | No broken requirements |
| Bandit | No medium/high findings; two reviewed low subprocess findings (B404/B603) |
| Render / CI YAML | Parsed locally; platform schema validation and remote runs pending |
| Source secret guard | 0 findings |

The two subprocess findings are expected for the decoder launcher: it uses a
fixed Python executable and trusted worker script, argument arrays with no shell,
generated server-owned paths, restricted environment, discarded output and a
bounded deadline. This review does not establish a full security sandbox.

Commands executed include backend `python -m pytest -q -p no:cacheprovider
--basetemp=../.tmp/phase10-final-tests`, `python -m bandit -r backend/app -ll`,
`python backend/scripts/check_secrets.py`, `python -m pip check`,
`python -m pip_audit --local --progress-spinner off`; frontend `npm run lint`,
`npm test`, `npm run build`, `npm run format:check`, `npm audit`; and
`python backend/scripts/e2e_frontend.py`. An ephemeral local server using
`scripts/start.py` ran `production_smoke.py --allow-local` with generated secrets
and synthetic documents; it was stopped afterward. No actual `.env` was changed.

An initial test run exposed local-mode startup incompatibility, which was fixed
by restricting startup model enforcement to production. A formatting failure
was corrected and checks rerun. Initial test temp-directory access needed an
approved subprocess-capable run with a workspace-owned temporary directory.

## Remaining release gates

1. Create/select the intended empty GitHub repository and authorize Git push,
   Render and Vercel accounts. No Git remote existed at inspection.
2. Run the Linux production-container job and all GitHub CI jobs. Docker's Linux
   engine is unavailable locally. Production NumPy 2.4.4 / SciPy 1.17.1 constraints
   support Python 3.11; local tests use installed Python 3.12.6 with newer versions.
   The complete pinned Linux environment has not been installed/tested here.
3. Validate actual Render resource limits, peak memory, latency and concurrency;
   test the image under adversarial load. The configured 2 GB plan is a starting
   budget, not a benchmark. All post-decode processing still runs in-process.
4. Configure actual frontend/backend origins, secrets and TLS, then run the
   live smoke script and deployed-browser workflow before recording URLs.
5. Review the weak raw NER measurements and manual accessibility limitations
   from Phase 9. Extraction is advisory and requires source review. Independent
   human relevance labels, multilingual validation and a custom NER model do not exist.
6. PostgreSQL round-trip and permission tests remain skipped locally; persistence
   stays disabled, so no production database/migrations were required or run.
7. Full hash-locking, base-image digest pinning and built-image advisory review
   remain outstanding supply-chain hardening. The model hash pins installed bytes,
   not independent publisher provenance. Current audits cover the local environment.

Phase 10 is paused at the requested account-authorization handoff. This document
records local preparation and does not claim successful public deployment.
