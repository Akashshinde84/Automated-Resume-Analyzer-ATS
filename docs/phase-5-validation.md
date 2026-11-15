# Phase 5 validation

Validated on 2026-11-15, Windows PowerShell, Python 3.12.6 and Node 22.19.0.
The requested Python 3.11 target is not installed and remains unverified.

## Results

- Full backend regression suite: **178 passed**, no skips, final run 6.58 seconds.
- All 138 earlier tests preserved; 40 matching/service/API cases added.
- Synthetic diagnostic evaluation: **10/10** annotated skill-set, importance,
  missing-evidence, overlap-score and status checks passed.
- Frontend production build passed: Vite 7.3.8, 42 modules transformed.
- `pip check`: no broken requirements found.
- One inherited Starlette/HTTPX TestClient deprecation warning remains.
- Generated matching sample was revalidated through `MatchingResponse`.

## Commands executed

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
Push-Location backend
.venv/Scripts/python.exe -m pytest tests/test_matching.py -q -p no:cacheprovider
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
Pop-Location
backend/.venv/Scripts/python.exe backend/scripts/evaluate_matching.py
backend/.venv/Scripts/python.exe -m pip check
npm --prefix frontend run build
git status --short
```

The initial sandboxed install could not reach the package index; elevated
installation succeeded into the existing virtual environment. Installed
scikit-learn 1.9.1 and its dependencies. Full tests used elevated permissions for
the existing synthetic document fixtures; Vite required subprocess access. No
global installation, external paid API, embedding download, commit, or deployment.

## Coverage

Identical/partial/unrelated/empty/unsupported descriptions; aliases and ambiguous
languages; required/preferred/unspecified headings and inline suffix markers;
conflicts and alternatives; weighted coverage and configurable defaults/overrides;
cosine feature contributions; exact evidence offsets and context; negated,
aspirational and not-required mentions; safe suggestions; personal-data and
name/company-only counterfactual invariance; instruction-like text; keyword
repetition; untrusted client skill arrays; parsed DOCX -> matching API; nested
OpenAPI; limits; and private validation/inference error responses.

All newly introduced tests passed. Before the final run, lexical features were
tightened so task words on name/company-only lines cannot affect cosine; they
must share a clause with affirmative ontology evidence. Two regression tests
cover this restriction and positive technical-duty matching.

## Evaluation evidence

See `evaluation/matching_pairs.json`, `evaluation/matching_results.json`, and
`evaluation/matching_results.md`. Selected outputs at default weights:

| Diagnostic case | Skill overlap | Lexical similarity | Overall |
| --- | ---: | ---: | ---: |
| Identical | 100.00 | 100.00 | 100.00 |
| Partial | 57.14 | 57.97 | 57.39 |
| Unrelated | 0.00 | 0.00 | 0.00 |
| Negated claim excluded | 50.00 | 57.97 | 52.39 |
| Empty / unsupported JD | unavailable | unavailable | unavailable |

This set was hand-authored to check implementation behavior. There are no hiring
outcomes, independent real-world corpus, accuracy estimates, calibration study,
or measured fairness assessment. Passing 10 handcrafted cases is not a claim of
real-world performance. The separate full sample includes duties and therefore
has different text similarity from the short partial diagnostic pair.

## Created/updated files

Added `app/schemas/matching.py`, `app/services/matching/` modules, API router,
service/API tests, evaluation script and fixtures, synthetic request/response, and
matching documentation. Updated app composition, body-limit coverage, settings,
`.env.example`, runtime requirements, README and architecture. Existing parser,
ontology and candidate extraction interfaces are preserved.

## Limits and scope

The score is a project-defined compatibility estimate, not an ATS score, hiring
probability, or automatic decision. TF-IDF uses canonical skills and a finite task
vocabulary, not unrestricted text or semantic embeddings. Requirement/negation
rules and ownership attribution are incomplete; unknown skills can be missed and
mixed excluded clauses can lose legitimate evidence. Personal attributes are not
features; basic counterfactual tests do not prove universal bias/proxy elimination.
Suggestions never fabricate qualifications. No persistence, OCR, ranking/dashboard,
custom-trained predictor, hiring workflow, or deployment was implemented.
