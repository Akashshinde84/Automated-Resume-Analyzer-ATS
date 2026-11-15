# Phase 9 QA report — 2026-11-15

**Decision: not production-ready.** Repeatable checks pass after fixes, but the
release blockers below remain. No deployment or GitHub workflow run is claimed.

## Passed checks

| Check | Result |
| --- | --- |
| Backend unit, API, parser, matching, report and security tests | **243 passed**, 2 skipped; one existing Starlette/httpx deprecation warning |
| Frontend unit/integration tests | **20 passed** |
| Real Chromium end-to-end workflows | **4 passed**, including keyboard dialog traversal and return focus |
| Axe WCAG 2 A/AA and 2.1 AA scans | **0 violations in 7 checked states**; four incomplete rule results still need manual review |
| Frontend lint, formatting, production build | Passed; Vite 7.3.8, 53 modules |
| npm advisory audit | Zero reported vulnerabilities |
| Python pip-audit, after updates | Zero reported advisories for auditable dependencies; **en-core-web-sm 3.8.0 skipped** because it is not on PyPI |
| Bandit application-source scan | Zero findings after replacing a flagged SAX import with equivalent HTML text escaping |
| Secret guard and `pip check` | Zero source findings; no broken requirements |
| Matching diagnostics | 10/10 requirement cases; 5/5 developer-labeled ranking queries, 15/15 strict pairwise checks |
| GitHub Actions definition | YAML structure validated; read-only permissions, SHA-pinned official actions, Python 3.11/3.12, disposable PostgreSQL, security/tests/build/browser jobs |

Synthetic browser screenshots were reviewed at desktop 1440px and mobile 390px.
Scanned PDF and missing-field states remain explicit. Automated accessibility is
not screen-reader, all-browser or full WCAG certification.

## Measured NLP results

Evaluated **20 independently authored fictional profiles: 10 PDF + 10 DOCX**.
Layouts include columns, tables, headers, bullets, a multipage PDF, alternate and
unsupported headings, Unicode, missing fields and ambiguous skill words.

| Metric | Precision | Recall | F1 | TP / FP / FN |
| --- | ---: | ---: | ---: | --- |
| Canonical skill values | 100.00% | 98.21% | **99.10%** | 55 / 0 / 1 |
| Raw pretrained PERSON/ORG values | 20.75% | 25.58% | **22.92%** | 11 / 42 / 32 |

Section presence: **137/140 binary decisions (97.86%)**; complete section sets:
**18/20 documents (90%)**. This does not measure boundary offsets.
Populated-field exact success: degree **9/10**, field **10/11**, company **13/14**,
title **14/15**, work-start/work-end **13/14** each. Explicit name **18/18**, email
**12/12**, phone **2/2**, institution **10/10**, project **7/7**, certification **3/3**.
These small denominators and explicit labels make the fixtures easier than real
resumes. Field-set recovery does not verify which values belong to which job.

These are **synthetic diagnostic measurements, not real-world accuracy claims**.
Gold is developer/agent authored, not independently human adjudicated. A missing
Data Analysis gold label was corrected after review and is disclosed in the
[annotation notes](evaluation/annotation-review.md). No extraction rules or ontology
were tuned to this corpus. Missing Go and unsupported headings remain visible.
No human-reviewed matching relevance labels, hiring outcomes, fairness evaluation,
custom-trained NER or calibrated probability estimates exist.

Evidence: [gold corpus](evaluation/resumes.json), [full metrics](evaluation/nlp_results.md),
[per-case errors](evaluation/nlp_results.json), [ranking diagnostics](evaluation/relevance_results.json).

## Fixed findings

Corrected measured contrast failures and dialog focus wrapping. Updated vulnerable
pip 24.2/filelock 3.32.7 to 26.3/4.2.10; final audits are clean for auditable packages.
Upload, cleanup, malformed content, XML entities, CORS, authorization, private logs,
report integrity and source secrets were checked. See the [security review](security-review.md).

## Not verified / remaining release blockers

1. **Live PostgreSQL and deployment role permissions:** Docker's engine is unavailable,
   so the round-trip and least-privilege probe are skipped locally. CI configures a
   disposable PostgreSQL service and separate NOLOGIN privilege probe; neither has
   run on GitHub yet. Actual production runtime credentials, grants, TLS and backups
   remain unverified. Use a migration role separately from a CRUD-only runtime role.
2. **NLP quality:** raw NER F1 is 22.92% on this corpus. Human-reviewed held-out,
   representative evaluation and approved quality criteria are needed before users
   rely on entities. Current extraction always requires source review; skill scores
   on this easy corpus do not establish broad reliability.
3. **Hostile-document resource controls:** input, expansion, pages and concurrency
   are bounded, but PDF parsing runs in application worker threads without a hard
   per-process CPU/memory/decompression deadline. Isolated processing and enforced
   host resource limits need validation before internet-facing untrusted ingestion.
   No destructive resource-exhaustion benchmark was run on the shared workstation.
4. **Release environment and reproducibility:** Python 3.11 is configured in CI but
   local tests use 3.12.6. GitHub Actions, deployed origins/TLS, load capacity and model
   supply-chain verification remain pending. The model is skipped by PyPI auditing;
   Python runtime ranges are not a fully hashed production lockfile.
5. **Manual accessibility:** incomplete axe results, screen readers, real-device,
   Safari/Firefox and broader keyboard flows still require review. OCR and complete
   PDF complex-script font/shaping support remain declared feature limitations.

## Reproduce

See [QA commands and CI guide](qa.md). Key commands from the repository root:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/evaluate_nlp.py
backend/.venv/Scripts/python.exe backend/scripts/evaluate_matching.py
backend/.venv/Scripts/python.exe backend/scripts/evaluate_relevance.py
backend/.venv/Scripts/python.exe backend/scripts/e2e_frontend.py
```

Phase 9 stops here. This report does not approve deployment readiness.
