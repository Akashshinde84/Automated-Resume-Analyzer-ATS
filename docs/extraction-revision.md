# Extraction revision — 2026-11-16

## Scope and original-file limitation

This modifies the existing parser/NLP/services/cards/reports. Anonymous automatic
upload, temporary-file cleanup, request limits, report signatures and private-history
protection remain. No paid API, custom training, login popup or resume-specific
candidate output was added.

The workspace contained only generated synthetic PDFs, not the original resume or
the reported eight-page user report. The original PDF was requested. The code-level
failure modes below were reproduced with fictional fixtures; the original file's
particular layout and embedded links **remain unverified**. A `[GitHub]` label without
an actual visible URL or embedded target cannot be recovered by guessing.

## Root causes and changes

| Reported issue | Reproduced cause | Change |
| --- | --- | --- |
| Missing LinkedIn/GitHub | The PDF parser used text containers only; it never read annotations. DOCX relationship targets were discarded. NLP contacts only saw preamble/contact text. | Capture bounded URI annotations and DOCX hyperlinks with labels, source, page/geometry and normalized-text anchor. Extract contact links and attach repository links to their actual project. Support evidenced mailto/tel targets without visiting them. |
| Institution/date loss | PDF container order and right-aligned fragments can separate institutions from qualification/date lines; record rules lacked HSC/SSC and separate AI & ML/grade handling. | Retain line boxes/font hints, infer simple column order, merge same-baseline fragments, group education locally, add qualification/specialization/grade rules and conservative section-local ORG fallback only with a degree. Missing dates remain null. |
| Descriptions and `[GitHub]` become projects | `item_blocks` treated almost any short non-bullet line as a new record, including bracket labels and sentence continuations. | Exclude metadata, link labels, dates/months and description cues from headers; retain bullet continuations; use explicit title labels and typography hints. Hyphenated titles remain intact. |
| `React.js` becomes a URL | A generic dotted-word regex plus automatic HTTPS prefix interpreted technology names as domains. | Visible URL matching requires HTTP(S), www, or a recognized GitHub/LinkedIn path. No bare dotted technology becomes a link. Captured actual targets are validated, not synthesized. |
| Certifications include activities, months and football bullets | Missing extracurricular boundary plus broad short-line header rule. | Add strict activities/other stop headings, month/date continuation rules, publisher labels/connectors/adjacent standalone publisher evidence, and a separate activities array. |
| Work experience missing | Only recognized section-local records were returned; empty output provided no distinction between absent heading and empty section. | Return `work_experience_status`: not_detected, section_empty or records_detected; explicit warnings avoid claiming the candidate has no experience. Add common internship/employment headings. |
| Eight-page repetitive report | Every skill occurrence and each complete raw record were printed repeatedly, then repeated in matching evidence. | Group skill names by category, retain at most two supporting match spans per comparison, omit duplicate raw records in PDF, preserve complete sources/spans in JSON. |

The font/column rule is deliberately heuristic, not a universal document-layout
model. A test caught repeated `[GitHub]` labels sharing the first anchor; geometry
now maps each annotation to its own line before record association.

## API/schema compatibility

`ResumeParser.parsefile(filepath)` still returns a JSON-serializable dictionary.
Existing text, sections, skills, warnings and metadata fields remain. Additions:

- `raw_text`, `layout_blocks` (line text/page/bbox/font size/bold), and `hyperlinks`
  (URL/label/source/page/bbox/block index/normalized text anchor).
- Education `grade`; project `technologies` while retaining `urls`; certification
  `description` and `urls`; candidate `summary` and `activities`.
- Extraction `work_experience_status`. `/extract` optionally accepts validated
  hyperlink/layout metadata; `/analyze` supplies it automatically from the parser.

Existing nested fields/defaults are retained. The integrated response, signed report
snapshot, JSON export, PDF export and frontend consume the same added fields. Reupload
after backend updates; receipts from an older snapshot schema may no longer verify.
No raw files are persisted. New provenance stays in the private in-memory response
and exports, not logs. URI targets are never requested by the server; unsafe schemes
and credential-bearing HTTP URLs are rejected. Mailto/tel become contact values,
not portfolio/project web links.

Publisher names form a small recognition vocabulary, not a candidate database.
For example Siemens, Persevex, Forage and NPTEL are assigned only when explicitly
labeled/connected or present as a standalone line directly after a certificate.
No issuer is inferred from a random mention or nonexistent resume content.

## Regression and evaluation evidence

`backend/tests/test_layout_extraction.py` reproduces dotted technology URL errors,
multiple/hyphenated projects, wrapped bullets, bracket labels, multiple education
records, B.Tech/HSC/SSC, grades, month/year continuations, issuer evidence,
certification/activity separation, missing-experience status, actual PDF annotations,
DOCX relationships/list formatting, two-column layout, unsafe links, embedded contacts,
decorated headings, ambiguous stack context and compact PDF evidence.

The supplemental tests create fictional documents at runtime. The existing labeled
corpus was also re-run: **20 fictional profiles, 10 PDF and 10 DOCX**, including
tables, headers, columns, multipage, Unicode and missing fields. Gold labels were
not changed. Old baseline files remain; revision results are separate:

- [Field precision/recall/F1 table](evaluation/extraction_revision_results.md)
- [Counts, model metadata, corpus hash and per-case errors](evaluation/extraction_revision_results.json)

Measured canonical skills: TP 55 / FP 0 / FN 1, precision 100%, recall 98.21%,
F1 **99.10%**, unchanged on this corpus. This does **not** establish perfect skill
extraction. Degree F1 **94.74%**, specialization F1 **95.24%**; company/work dates
F1 **96.55%**, job title F1 **93.75%** on their small labeled value sets. A newly
recognized internship section still exposes an unresolved comma-delimited role
header error; the per-case output retains this false positive/missing clean title. Project
and certificate value counts are only seven and three populated examples, respectively.
New embedded-link/grade/activity fields are tested separately, not falsely included
in gold that never labeled them.

Raw pretrained PERSON/ORG F1 is **22.00%**, versus historical **22.92%**. Reading-order
and line-break changes affect NER context; raw NER quality has not improved. Explicit
record heuristics must not be confused with trained-model accuracy. Section presence
is **178/180** decisions with the current nine-section vocabulary; exact section sets
are **18/20**. Its denominator differs from the historical seven-section evaluation.
These are reused synthetic diagnostics, not representative or independently human-
adjudicated held-out evaluation. Value sets do not prove correct cross-record alignment.

Reproduce from the repository root:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/evaluate_extraction_revision.py
backend/.venv/Scripts/python.exe -m pytest backend/tests -c backend/pytest.ini
backend/.venv/Scripts/python.exe backend/scripts/e2e_frontend.py
Set-Location frontend
npm run lint
npm test
npm run build
npm run format:check
```

Final validation: **273 backend tests passed, 3 skipped**, one existing Starlette/httpx
deprecation warning; **19 frontend tests passed**; **4 real Chromium workflows passed**.
Frontend lint/format/build, local anonymous smoke and source secret guard passed.
Bandit has no medium/high findings; two previously reviewed low subprocess warnings
remain. Skips are two unavailable PostgreSQL probes and the Linux-only resource test.
The backend was restarted and the local smoke rerun after readiness; the first immediate
post-restart probe had raced startup, then the ready service passed the full flow.

A synthetic full-flow
JSON/PDF comparison report rendered to **three pages**; all pages were rendered and
visually reviewed for spacing, wrapping, headers and footers. This is not a measured
eight-to-three-page reduction on the unavailable original resume. The PDF remains
bounded by its presentation budget; JSON keeps full structured evidence.

## Remaining limits

- Original private PDF and its eight-page output have not been validated. Supply the
  original PDF for consented inspection; the report alone cannot establish text order,
  annotation presence or layout geometry.
- Complex overlapping columns, rotated pages, unusual typography, wrapped section
  headings, unusual institutions and ambiguous unlabelled record boundaries can still
  fail. Ambiguous title/description lines require source review; retained raw text and
  layout permit inspection. No universal multi-column accuracy claim is made.
- Pretrained English NER remains weak; no custom model was trained. Generic ORG is
  not automatically a degree or employer. Dates without sufficient context stay null.
- OCR is still unavailable. Image-only PDFs return warnings and no invented text;
  actual annotation targets, if present, may still supply evidenced contact links.
- Existing font/script-shaping, Linux-container/load and manual accessibility release
  gates remain. There is no live deployment or production-readiness claim.
