# Annotation review and evaluation scope

All 20 profiles are fictional and authored for this project under CC0-1.0.
Their source paragraphs and gold labels are version controlled in `resumes.json`.
Gold was written before running extraction. The evaluator generates PDF/DOCX files
temporarily rather than committing personal document binaries.

Developer review found two annotation-format issues:

- Before prediction, AWS was changed to its existing ontology canonical name,
  Amazon Web Services; resume source text and ontology were unchanged.
- After inspecting mismatches, r10's gold skills omitted Data Analysis despite the
  literal skill phrase being asserted in the source. It was added to gold. This
  annotation correction is disclosed rather than counted as a model improvement.

No extraction rules or ontology aliases were tuned on the corpus. Remaining
misses, including unsupported Programming Languages/Career History/Training
headings, remain visible in the measured result. The strong explicit name/contact
labels make field extraction easier than many real resumes. The corpus includes
10 PDF and 10 DOCX profiles, single/two-column PDFs, a multipage PDF, DOCX tables,
header content, bullets, inline aliases, missing names/employers/dates/skills,
Unicode text and ambiguous ordinary-language skill words.

This is not independent human annotation. No inter-annotator agreement, representative
sampling or held-out real-world test set exists. Unique exact-value PERSON/ORG
metrics must not be confused with token BIO/span metrics or candidate-field
heuristic success. Seven-way binary section presence is not boundary accuracy.
Field-set recovery does not validate correspondence between multiple records.

Matching has 10 developer-annotated requirement regressions and 5 developer-labeled
three-level ranking queries. No human-reviewed relevance labels were supplied or
obtained, and no human relevance accuracy is claimed. Hiring outcomes, demographic
fairness, calibrated scores and production generalization remain unevaluated.
