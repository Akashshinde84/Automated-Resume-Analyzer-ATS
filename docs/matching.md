# Resume-to-job matching (Phase 5)

`POST /api/v1/resumes/match` compares a Phase 4 parsed resume with pasted job text.
It returns typed evidence, requirement coverage, lexical TF-IDF similarity, and a
project-defined compatibility estimate. It is **not a real ATS score, hiring
probability, qualification verification, or hiring/rejection recommendation**.
No decision threshold, ranking workflow, or automatic hiring action is provided.

## Install and run (Windows PowerShell)

From the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
Push-Location backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
Pop-Location
```

Matching adds scikit-learn; it does not need a paid API, downloaded embedding
model, or pretrained spaCy NER. The existing Phase 3 model is unrelated to this
matching baseline. Open http://localhost:8000/docs for the typed request/response.

Try the synthetic example from a second terminal:

```powershell
curl.exe -X POST 'http://localhost:8000/api/v1/resumes/match' -H 'Content-Type: application/json' --data-binary '@docs/examples/matching.request.json'
```

Example request shape:

```json
{
  "resume": {"text": "Skills: Python, SQL"},
  "job_description": "Required: Python, SQL; Preferred: Docker",
  "weights": {"skills": 0.7, "text": 0.3}
}
```

You may pass the entire `/api/v1/resumes/parse-text` response as `resume`. Only
`resume.text` is used; supplied skill arrays, names, metadata, scores, and section
claims are ignored and ontology evidence is re-extracted. Review parsing warnings
separately; matching does not re-run file extraction or OCR. The text should use
recognizable professional headings (Skills, Experience, Projects, Summary,
Certifications). Unheaded/preamble/contact/education text is not scored. This is a
conservative evidence filter, and may miss skills in unusual layouts.

Direct Python use:

```python
from app.services.matching import MatchingService
from app.schemas.matching import MatchingWeights

result = MatchingService().match(
    parsed_resume={"text": "Skills: Python, SQL"},
    job_description="Required: Python, SQL; Preferred: Docker",
    weights=MatchingWeights(skills=0.8, text=0.2),
)
json_result = result.model_dump(mode="json")
```

The parser and Phase 3 `/extract` responses are unchanged. No frontend matching
screen, persistence, or deployment is added. Resume text is limited to 100,000
characters, JD text to 50,000, and the full HTTP body to 2 MiB, including chunked
requests. If ancillary parser data makes the body too large, send only its `text`.
Invalid schemas/weights return sanitized 422; body overflow returns 413; unexpected
inference failure returns sanitized 503. Bodies and exception contents are not logged.

## Job requirement interpretation

The Phase 4 ontology and literal/context-aware alias matching normalize both sides.
Examples: JS -> JavaScript, ReactJS -> React, AWS -> Amazon Web Services. Java does
not match inside JavaScript. Ambiguous R/Go use the existing contextual gates.

Required headings include Required Skills, Requirements, Minimum Qualifications,
Must Have, Essential, and Mandatory. Preferred headings include Preferred Skills,
Nice to Have, Bonus, and Desirable. Colon markers, semicolon clauses, some suffix
labels (`Python required, Docker preferred`), and repeated sections are supported.
Responsibilities/Duties reset importance to unspecified. Company/benefits sections
are excluded. Unlabeled mentions remain **unspecified**, rather than being silently
promoted to mandatory requirements.

Alternative groups such as `Python or Java` are left unspecified with a review
warning; this baseline does not implement Boolean requirement satisfaction. If the
same skill has conflicting labels, required takes precedence over preferred, then
unspecified, and all job evidence is retained with a warning. Explicit negated or
not-required mentions are excluded. Negation and scope rules are intentionally
conservative and incomplete; they are not a full language understanding model.

## Scoring formula

Let J be the unique affirmative supported job skills and m_i be 1 if qualifying
resume evidence for skill i is present, otherwise 0. Every job skill belongs to one
importance group. Defaults:

- required importance a_i = 2
- preferred importance a_i = 1
- unspecified importance a_i = 1

Skill overlap is job-side weighted coverage:

```text
S = 100 * sum(a_i * m_i for i in J) / sum(a_i for i in J)
```

Missing preferred skills affect coverage, but are reported separately from missing
required skills. Additional resume skills do not increase this coverage denominator.
A match establishes only an affirmative textual mention, not proficiency.

For both resume and JD, the same representation function creates:

1. One token per canonical ontology skill with accepted affirmative evidence.
2. Allowlisted task concepts (build, test, deploy, maintain, design, backend,
   frontend, pipeline, API, automate, document, analyze) from clauses containing
   accepted skill evidence. Variants such as built/building/developed map to build.

Only those finite tokens enter the vectorizer: arbitrary words, names, company or
institution names, locations, ages, dates, contact details, gender, and other
personal attributes are not features. Task words from name/company-only lines do
not enter similarity. Resume inclusion is restricted to the professional sections
listed above; personal/instruction-like clauses on either side are excluded.

The baseline is scikit-learn `TfidfVectorizer` with binary term frequency, shared
pair-local vocabulary/IDF, smooth IDF, and L2 normalization. With two documents:

```text
tf(t,d) = 1 if token t appears in d, otherwise 0
idf(t) = log((1 + 2) / (1 + df(t))) + 1
v_d = L2_normalize(tf(t,d) * idf(t))
T = 100 * cosine(v_resume, v_job)
```

Zero-feature sides give T=0. No empty-vocabulary fit is attempted. Binary frequency
means repeating a keyword cannot improve its weight. Aliases share a token. The
response includes each shared feature's contribution to cosine; their sum times
100 equals the unrounded T. See the official
[TF-IDF vectorizer documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html)
and [cosine similarity documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html).

This deliberately constrained representation loses arbitrary duty/domain wording
in exchange for minimizing personal-information influence. **T is lexical/text
similarity, not embedding-based semantic similarity.** Fitting on a pair does not
train a qualification predictor, and scores are not calibrated across job postings.

Overall defaults to:

```text
overall = 0.70 * S + 0.30 * T
```

All computed components and the overall are bounded to 0-100 and rounded to two
decimals. Overall uses unrounded components, so reconstructing it from displayed
components can differ slightly. Response `weights`, `effective_weights`, `formula`,
`method`, and `ontology_version` make the computation reviewable.

If either input is blank, scores are null with `status: insufficient_input`. If no
supported affirmative job skills are found, scores are null with
`status: no_supported_job_skills`. Unknown requirements are not counted as perfect
coverage or automatically assigned a zero. The overall is not reweighted to hide
missing information. Nonempty resume text with no supported professional evidence
can receive zero coverage for a supported JD, alongside a missing-evidence warning;
this does not establish lack of ability.

## Weight configuration

Backend default in `backend/.env.example`:

```dotenv
MATCHING_WEIGHTS={"skills":0.7,"text":0.3,"required_importance":2.0,"preferred_importance":1.0,"unspecified_importance":1.0}
```

Process environment overrides `.env`. A request's optional `weights` overrides
server defaults as a complete `MatchingWeights` object, using schema defaults for
omitted properties. It is not a partial merge into custom server defaults.
Skills/text weights must be finite, between 0 and 1, and sum to 1. Importance values
must be finite, strictly positive, and at most 100. No model learns these weights. Skill coverage and lexical similarity share
ontology features and are correlated; they are not independent measures or
statistically calibrated evidence. Changing weights changes the project policy,
so record and review those changes.

## Evidence and improvement suggestions

`MatchingResponse` includes:

- Scores, actual configuration, formula, method, status, ontology version, warnings.
- Required skills, preferred skills with matched flags, and unspecified skills.
- Matched skills with job and resume evidence; missing required skills with JD evidence.
- Exact half-open character spans, source sections, and bounded nearby text context.
- Shared feature contributions and structured suggestions.

Resume offsets refer to the supplied `resume.text`, and JD offsets to the supplied
JD, without rewriting the input. Matching does not rely on client-provided spans.
Evidence and surrounding text are sensitive response data and must not be logged.

Suggestions are deterministic and grounded: they may make existing affirmative
resume evidence easier to find, explicitly conditioned on it reflecting actual
experience. For missing required/preferred evidence, they ask the user to review
that criterion against their background and explicitly say not to list unsupported
skills. They do not invent qualifications, degrees, jobs, years, proficiency,
projects, measured outcomes, or recommend keyword stuffing. Learning/aspirational
and recognized negated mentions do not establish possession. Missing textual
evidence is not proof that the person lacks the skill.

## Evaluation and limitations

Reproduce the hand-authored diagnostic evaluation:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/evaluate_matching.py
```

Inputs and skill/status annotations are in
[evaluation/matching_pairs.json](evaluation/matching_pairs.json). The
[generated report](evaluation/matching_results.md) and
[JSON results](evaluation/matching_results.json) cover 10 cases: identical,
partial, unrelated, aliases, negation, preferred-only, empty, out-of-ontology,
instruction-like text, and a personal-data counterfactual. All 10 match their
handwritten expected skill sets, status, and coverage score. This is a diagnostic
regression set, **not a real-world accuracy, fairness, calibration, or hiring-outcome
study**. No accuracy or hiring-probability claim is made.

Known limits: finite ontology/task coverage, English headings/rules, incomplete
negation and conjunction scope, noisy parser layouts, unclear skill ownership,
ambiguous names colliding with technical vocabulary, and unsupported alternative
logic. Excluding personal/mixed clauses can also discard legitimate technical
content. Recognized protected/personal criteria are excluded and counterfactual
tests pass, but these heuristics do not prove absence of every proxy or bias in
arbitrary text. It is not a verified, production hiring assessment. Require human
review of evidence and job criteria; never use the number as an automatic hiring
or rejection decision. No OCR, background verification, private external data,
semantic embeddings, custom training, database, ranking UI, or deployment is added.
