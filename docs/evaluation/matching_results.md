# Synthetic matching evaluation

10/10 handwritten diagnostic cases match their annotated skill sets, status and overlap score.

| Case | Skill overlap | Lexical similarity | Overall | Annotation check |
| --- | ---: | ---: | ---: | --- |
| identical | 100.0 | 100.0 | 100.0 | pass |
| partial | 57.14 | 57.97 | 57.39 | pass |
| unrelated | 0.0 | 0.0 | 0.0 | pass |
| aliases | 100.0 | 100.0 | 100.0 | pass |
| negated | 50.0 | 57.97 | 52.39 | pass |
| preferred_only | 50.0 | 57.97 | 52.39 | pass |
| empty_resume | None | None | None | pass |
| out_of_ontology | None | None | None | pass |
| instruction_attack | 0.0 | 0.0 | 0.0 | pass |
| personal_counterfactual | 100.0 | 100.0 | 100.0 | pass |

Scores are project-defined estimates, not ATS scores or hiring probabilities. None means unavailable.

This hand-authored set exercises expected behavior, not generalization. It has no hiring outcomes, independent real-world test corpus, demographic coverage, measured fairness, or calibration. Passing these cases is not an accuracy claim.

Reproduce: `backend/.venv/Scripts/python.exe backend/scripts/evaluate_matching.py` from the repository root.
