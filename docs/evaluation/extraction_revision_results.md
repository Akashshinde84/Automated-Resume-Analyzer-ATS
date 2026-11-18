# Extraction revision: measured synthetic diagnostics

20 fictional profiles (10 PDF, 10 DOCX), unchanged gold labels.
This is a reused diagnostic corpus, not representative or independently adjudicated validation.

| Measure | Precision | Recall | F1 | TP / FP / FN |
| --- | ---: | ---: | ---: | --- |
| Canonical skills | 100.00% | 98.21% | 99.10% | 55 / 0 / 1 |
| Raw pretrained PERSON/ORG | 19.30% | 25.58% | 22.00% | 11 / 46 / 32 |
| name | 100.00% | 100.00% | 100.00% | 18 / 0 / 0 |
| emails | 100.00% | 100.00% | 100.00% | 12 / 0 / 0 |
| phones | 100.00% | 100.00% | 100.00% | 2 / 0 / 0 |
| institution | 100.00% | 100.00% | 100.00% | 10 / 0 / 0 |
| degree | 100.00% | 90.00% | 94.74% | 9 / 0 / 1 |
| field | 100.00% | 90.91% | 95.24% | 10 / 0 / 1 |
| company | 100.00% | 93.33% | 96.55% | 14 / 0 / 1 |
| job_title | 93.75% | 93.75% | 93.75% | 15 / 1 / 1 |
| work_start | 100.00% | 93.33% | 96.55% | 14 / 0 / 1 |
| work_end | 100.00% | 93.33% | 96.55% | 14 / 0 / 1 |
| project | 100.00% | 100.00% | 100.00% | 7 / 0 / 0 |
| certification | 100.00% | 100.00% | 100.00% | 3 / 0 / 0 |

Section presence: 178/180; exact section sets: 18/20.
Presence denominators differ from the old seven-section baseline because activities/other boundaries are now recognized.

Fields compare normalized value sets; they do not establish correct record-to-record association.
New hyperlink/wrapped-record/layout cases are covered separately by test_layout_extraction.py; the original corpus does not label these new fields.
The high precision of several fields reflects a small, easy set with few populated examples, not a general accuracy guarantee.
Raw NER remains weak and has not improved: 22.00% F1 versus the historical 22.92%; text reading-order changes alter its context.
No custom model was trained. Full per-case errors, model metadata and dataset SHA-256 are in the companion JSON.

Reproduce: `backend/.venv/Scripts/python.exe backend/scripts/evaluate_extraction_revision.py`.
