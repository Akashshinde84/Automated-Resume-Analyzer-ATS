# PDF upload investigation

## Follow-up: observed validation crash

Support reference `baa42106a6c5` in `.tmp/restart-backend.err.log` records
`code=parsing_worker_failed exit=3 stage=decode exception_type=ValidationError
elapsed_ms=1842`. This observed failure is an application validation error,
not a reported resource-limit or timeout failure.

A deterministic reproduction found that `HEADINGS` recognizes `activities` and
`other`, while `SkillSpan.section` omitted both values. A Python skill mention
under "Extra Curricular Activities" or "Interests" raised a Pydantic
`literal_error` at `section`. The schema now accepts both recognized sections;
evidence retains `source_type=other` and is not marked explicitly listed.
Regression tests cover every recognized section and both failing headings through
the isolated anonymous PDF upload endpoint. The original private PDF is still
needed to confirm its complete contents and analysis.

The reported file `Akash_Shinde_net (4).pdf` was not present in the workspace.
The available local backend log contains startup messages only. The original
upload failure therefore cannot yet be attributed to PDF parsing, memory, CPU,
wall-clock time, or model initialization. Reproduce with the original PDF before
claiming a cause or changing limits.

## Confirmed diagnostic defect

The committed `backend/app/services/isolated_parser.py` combined a nonzero decoder
exit, a missing result, and an oversized result into `parsing_resource_limit`:
"Document processing exceeded a resource limit or failed safely."
Worker stderr was discarded. This proves the message was ambiguous; it does not
prove that a 188.4 KB file exceeded the 10 MB upload limit.

The pre-existing working-copy revisions separate decoder failure codes, emit a
content-free reference, stage and exception class, terminate owned worker trees
on timeout, and remove result/diagnostic temporary files. They also use one PDF
page traversal and keep lightweight date utilities outside the NLP package.
The model cache and inference lock reuse spaCy in the API process.

This investigation additionally corrected silent NLP exception handling in both
analysis endpoints. Unexpected inference failures now return HTTP 500 with
`extraction_failed` and `diagnostic_id`; backend logs contain that reference,
stage and exception class without exception messages or tracebacks.

## Verification

- Backend suite: 292 passed, three skipped before the added full PDF workflow
  test. The skips cover Linux resource primitives and optional PostgreSQL tests.
- Frontend: lint, production build, and all 20 unit/integration tests passed.
- Real browser: all four workflow tests passed, including anonymous automatic
  upload, retry, real results, and JSON/PDF downloads.
- `test_pdf_upload_workflow.py` adds one synthetic PDF covering all requested
  candidate sections, project-description grouping, technology URL rejection,
  and signed JSON/PDF report downloads without credentials.

Windows cannot validate production Linux RLIMIT enforcement. Existing Linux CI
and disposable-process tests retain those checks. No resource limits were raised
or disabled in this investigation. OCR remains unavailable; scanned PDFs return
explicit warnings and no inferred text. Existing uncommitted work was preserved.

## Original-file follow-up

Upload the original PDF to the isolated anonymous analysis endpoint. If it fails,
correlate the response's `diagnostic_id` with the backend diagnostic line. Inspect
the recorded stage, exception class, exit classification and elapsed time. Do
not infer OOM from an unexplained process termination. Never log resume contents,
client filenames, credentials, or raw exceptions.
