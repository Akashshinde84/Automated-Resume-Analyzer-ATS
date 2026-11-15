# Synthetic NLP evaluation

20 profiles: {'pdf': 10, 'docx': 10}. Dataset SHA-256: `8d32fad5deb665b9dd2141aaa33aa2be912fd952c34e366f9ab1d647128b0e4c`.

| Measure | Precision | Recall | F1 | TP / FP / FN |
| --- | ---: | ---: | ---: | --- |
| Skills | 100.00% | 98.21% | 99.10% | 55 / 0 / 1 |
| Pretrained NER | 20.75% | 25.58% | 22.92% | 11 / 42 / 32 |
| PERSON | 35.00% | 38.89% | 36.84% | 7 / 13 / 11 |
| ORG | 12.12% | 16.00% | 13.79% | 4 / 29 / 21 |

Section presence: 137/140 = 97.86%. Exact section sets: 18/20 = 90.00%.

| Field | Correct complete populated cases | Populated success | Exact cases including empty |
| --- | --- | ---: | --- |
| name | 18/18 | 100.00% | 20/20 |
| emails | 12/12 | 100.00% | 20/20 |
| phones | 2/2 | 100.00% | 20/20 |
| institution | 10/10 | 100.00% | 20/20 |
| degree | 9/10 | 90.00% | 19/20 |
| field | 10/11 | 90.91% | 19/20 |
| company | 13/14 | 92.86% | 19/20 |
| job_title | 14/15 | 93.33% | 19/20 |
| work_start | 13/14 | 92.86% | 19/20 |
| work_end | 13/14 | 92.86% | 19/20 |
| project | 7/7 | 100.00% | 20/20 |
| certification | 3/3 | 100.00% | 20/20 |

## Scope and limitations

- Synthetic developer-authored diagnostic set; not independently human reviewed or representative.
- No held-out real-world corpus, confidence intervals, hiring outcomes, fairness or calibration claim.
- Entity scores compare unique exact normalized PERSON/ORG values per resume, not BIO spans.
- Field sets measure value recovery, not alignment of multiple employment/education records.
- Section accuracy measures seven binary presence decisions per document, not boundary offsets.

Gold labels were authored before predictions. No human relevance adjudication or custom NER training occurred. Per-case errors and model availability are in nlp_results.json. Do not interpret high synthetic skill scores as real-world accuracy.

Reproduce from repository root: `backend/.venv/Scripts/python.exe backend/scripts/evaluate_nlp.py`.
