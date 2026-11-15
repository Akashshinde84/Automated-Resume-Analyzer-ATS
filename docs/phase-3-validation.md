# Phase 3 validation

Validated on 2026-11-15 in Windows PowerShell, Python 3.12.6 and Node 22.19.0.
Python 3.11 remains the requested target but is unavailable on this machine.

## Results

- Full backend suite: **95 passed**, no skips, in 4.30 seconds on the final run.
- Includes all 44 Phase 1/2 tests and 51 Phase 3 cases.
- Real pretrained NER smoke test passed with PERSON and ORG predictions.
- Frontend production build passed: Vite 7.3.8, 42 modules transformed.
- `pip check`: no broken requirements found.
- Synthetic sample was generated with the real model and validated back through
  `ExtractionResult`; it contains one education, one job, one project, and two
  certifications. Missing issuer/date fields remain null.
- One inherited Starlette/HTTPX TestClient deprecation warning remains.

## Commands executed

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m spacy download en_core_web_sm
Push-Location backend
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
Pop-Location
backend/.venv/Scripts/python.exe -m pip check
npm --prefix frontend run build
git status --short
```

Inspected all application source, tests, configuration and previous documentation
before implementation. Generated frontend dependency lock content was preserved.
The first sandboxed package installation failed to reach the index; elevated
installation succeeded into the existing project virtual environment. Tests used
elevated temporary-file permissions and Vite used elevated subprocess access.
No global install, commit, remote, deployment, or custom model training occurred.

Installed spaCy 3.8.18, phonenumbers 9.0.43, and official `en_core_web_sm` 3.8.0.
The pretrained model is a separate installation, documented in the README. Runtime
code never downloads a model automatically.

## Coverage and corrections

- Explicit and heuristic candidate names; accented, Indic, Arabic, CJK, curly
  apostrophe names and ambiguous PERSON/ORG cases.
- Multiple emails and links; exact URL host checks; no promotion of arbitrary
  websites or education/reference contacts to candidate contact fields.
- UK, US, Indian, and French international phones; national numbers with and
  without region; invalid phones, extensions, inline contacts, date/ID exclusions.
- Institution and degree heuristics, including US dotted abbreviations and curly
  possessives; field connectors; multiple degree-first and institution-first
  records; partial dates; unassigned ambiguous single dates.
- Multiple jobs without blank lines, title-first/company-first/inline headers,
  pretrained ORG assistance, and ambiguous/missing employers and titles.
- Project/certification records and URLs, missing issuer/date/ID fields.
- Missing-model fallback and actual pretrained inference. Manually annotated Doc
  tests are adapters/test doubles, not evidence of training or measured accuracy.
- Nested OpenAPI/Pydantic schemas, input/body limits, and private validation,
  inference-error, and success paths; no sensitive request markers in logs.
- Phase 2 DOCX upload -> normalized text -> Phase 3 candidate extraction.

Fixed a year range being detected as a phone and a PowerShell encoding issue in
curly-apostrophe degree matching. Explicitly avoided assigning unlabeled education
years to graduation. Ambiguous multi-organization headers leave employer null.

## Limits

See `nlp-extraction.md` for supported patterns, method differences and limitations.
English NER is not universally accurate across scripts/languages. Degree/title/
institution vocabularies and record boundaries are heuristic, not a benchmarked
resume model. Day-level/fuzzy date parsing, OCR, skills, matching, persistence,
frontend upload/dashboard, and production deployment remain out of scope.
