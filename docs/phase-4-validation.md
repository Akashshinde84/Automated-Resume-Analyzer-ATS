# Phase 4 validation

Validated on 2026-11-15 with Windows PowerShell, Python 3.12.6 and Node 22.19.0.
The requested Python 3.11 target is still unavailable on this machine.

## Results

- Full backend suite: **138 passed**, no skips, final run 7.80 seconds.
- All 95 Phase 1/2/3 tests preserved; 43 new Phase 4 cases passed.
- Frontend production build passed (Vite 7.3.8, 42 modules transformed).
- `pip check`: no broken requirements found.
- Ontology: **137 canonical skills**, **8 categories**, version **1.0.0**.
- No dependencies, model downloads, paid APIs, or API keys added.
- One inherited Starlette/HTTPX TestClient deprecation warning remains.

## Commands executed

```powershell
Push-Location backend
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
Pop-Location
backend/.venv/Scripts/python.exe -m pip check
npm --prefix frontend run build
git check-ignore backend/app/data/skills.json
git status --short
```

The ontology is not ignored (`git check-ignore` correctly returns exit status 1
with no output). New source files remain available for review with the rest of
this uncommitted workspace. No commit, remote, or deployment was created.

Tests used elevated execution for synthetic temporary PDF/DOCX fixtures. The Vite
build used elevated subprocess access, consistent with prior sandbox limitations.
No source dependency installation was necessary. The full synthetic parser sample
was generated from a DOCX; the temporary DOCX was removed after generating JSON.

## Coverage and fixes

- Required category coverage and strict ontology schema/collision validation.
- React/React.js/ReactJS, JS/JavaScript, ML/Machine Learning and other aliases.
- Java versus JavaScript, SQL versus MySQL, identifiers and Unicode boundaries.
- Literal C++, C#, .NET, Node.js, CI/CD and longest overlapping phrases.
- Unicode punctuation/nonbreaking spaces and exact supporting character offsets.
- Canonical deduplication retaining every occurrence and its source context.
- Repeated/inline sections, CRLF, empty text, and empty sections.
- R/Go/C context gates, R&D and ordinary prose exclusions, volume-unit ML exclusion.
- Framework project-table cells and Render hosting versus rendering prose.
- URL/email/qualified-name exclusions and custom Unicode ontology aliases.
- PDF parser integration, DOCX upload API integration, and empty PDF skill results.
- Skill extraction without loading a pretrained spaCy model.

The first run passed 134 cases and exposed a standalone React project-cell miss.
The corrected context rule and additional regression cases passed on the final run.

## Changed files

Added `app/data/skills.json`, `app/schemas/skills.py`, `app/services/skills.py`,
`app/services/sections.py`, and `tests/test_skills.py`. Updated the parser to share
heading detection and add skill results. Added the skill guide and synthetic JSON;
updated README/architecture. Previous phase reports and APIs are preserved.

## Remaining limits

No proficiency, negation interpretation, implied/prerequisite skills, fuzzy or
multilingual matching, scoring, persistence, OCR, UI/dashboard, or deployment was
added. Heading/ambiguity rules are heuristics; unknown aliases and wrapped phrases
can be missed. Supporting mentions do not prove skill mastery or ownership.
See `skills.md` for adding reviewed skills and testing their ambiguity policies.
