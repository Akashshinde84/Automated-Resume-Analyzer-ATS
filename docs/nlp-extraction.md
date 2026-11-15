# NLP and candidate extraction (Phase 3)

The extractor accepts normalized text from Phase 2. It does not replace the parser
or modify `/parse-text` responses. `POST /api/v1/resumes/extract` accepts JSON and
returns the nested Pydantic `ExtractionResult` schema, visible in `/docs`.

## Local setup and use

From the repository root in Windows PowerShell:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m spacy download en_core_web_sm
Push-Location backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
Pop-Location
```

`SPACY_MODEL=en_core_web_sm` is the default in `backend/.env.example`. The model
is installed separately from spaCy. A missing model gives explicit `nlp.status:
"unavailable"` and a warning; regex/heuristics still run. Model inference failure
returns sanitized HTTP 503. There is no automatic model download during requests.
Restart the server after installing or changing the model (the adapter caches it).

To try the committed synthetic example in another terminal:

```powershell
$text = Get-Content docs/examples/synthetic-resume.txt -Raw -Encoding utf8
$body = @{ text = $text; phone_region = $null } | ConvertTo-Json
$response = Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/resumes/extract' -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$response | ConvertTo-Json -Depth 20
```

For real documents, first send the file to `/api/v1/resumes/parse-text`, then pass
its `text` to `/api/v1/resumes/extract`. Check parser warnings separately. A PDF
with no text produces empty candidate fields; OCR is still not implemented.
No file is stored and no API/UI for persistent candidate records is added.

Direct Python use from `backend/`:

```python
from app.services.parser import ResumeParser
from app.services.extraction import InformationExtractor

parsed = ResumeParser().parsefile("C:/path/to/resume.docx")
result = InformationExtractor().extract(parsed["text"], phone_region=None)
json_dictionary = result.model_dump(mode="json")
```

Input is capped at 100,000 characters, with a 601,024-byte HTTP body limit that
also applies without Content-Length. Oversized bodies return 413. Schema errors
return 422 without echoing input content. No resume truncation is performed.
An empty input returns 200 with null/empty fields and a warning. Direct Python
calls validate the same character limit and phone region.

## What each technique does

| Technique | Use here | What it cannot establish |
| --- | --- | --- |
| Regex | Email syntax, URL candidates/hosts, explicit date ranges and labeled credential IDs | Deliverability, identity, URL ownership, or semantic relationships |
| Heuristics | Candidate header/Name label, university vocabulary, explicit degree vocabulary, role vocabulary, section-local record boundaries | Reliable understanding of arbitrary layouts or every institution/degree/title |
| Pretrained NER | Official spaCy `en_core_web_sm` PERSON/ORG spans; introductory PERSON and unambiguous organization headers provide baseline evidence | A PERSON is not automatically the candidate; an ORG is not automatically a university/employer; generic NER is not a degree recognizer |
| Custom-trained NER | **Not implemented or trained** | Would require labeled resume data, privacy controls, train/validation/test splits, evaluation, and separate deployment/versioning |

The official model package is version 3.8.0 in this validation environment, using
spaCy 3.8.18. See the [spaCy model guide](https://spacy.io/usage/models) and
[EntityRecognizer API](https://spacy.io/api/entityrecognizer) for baseline behavior.
Tests with manually annotated spaCy Docs and a deterministic provider are test
doubles, not trained models; a separate smoke test executes the real model.

## Schemas and evidence

`app/schemas/candidate.py` defines Candidate, PhoneNumber, Education,
WorkExperience, Project, Certification, Evidence, NamedEntity, NLPMetadata,
ExtractionRequest, and ExtractionResult. Unknown input properties are rejected.

- Candidate has nullable `name`, email/phone/link arrays, and nested record arrays.
- Education has nullable `institution`, `degree`, `field`, `start_date`, `end_date`.
- Work experience has nullable `company`, `job_title`, dates, and `description`.
- Projects have nullable name/description and URLs. Certifications have nullable
  name, explicitly labeled issuer/credential ID, and date.
- Each record retains `raw_text`, provenance, and warnings so an uncertain split
  or unrecognized field can be reviewed. The top-level candidate has contact/name
  provenance. Raw text/evidence is sensitive response data, never log data.
- Evidence records its field, rule, method, source text, and optional qualitative
  confidence. `low`/`medium`/`high` describes rule strength, not a measured accuracy
  or calibrated probability. Pretrained entity confidence is `null`; this adapter
  does not have calibrated per-entity probabilities.
- Baseline `entities` are separate from assigned candidate fields. Character
  offsets refer to the NFC/whitespace-normalized text, not the original raw input.
- `nlp` reports the configured model, actual package version when loaded, language,
  availability, and `custom_trained: false`.

Education degrees use explicit vocabulary (e.g. BSc/B.S., Bachelor of Science,
Master's, MBA, PhD), independent of ORG NER. Fields use an explicit connector,
label, or a small known-field vocabulary after the degree. Institutions use
university/college/institute/school vocabulary or an explicit label. Unknown
institutions and degrees are not guessed from arbitrary ORG tags.

Experience boundaries use repeated short company/title/date headers; both
company-first and title-first layouts and inline `Title | Company | Dates` or
`Title at Company` are supported. Clear company labels/suffixes and unique
section-local ORG headers can identify an employer. Multiple organizations in
one header do not establish the employer; company remains null. Descriptions
and original block text are retained. No job title is inferred from duties.

Dates preserve explicit precision: `2020`, `2021-04`, or `present`. English month
names and MM/YYYY normalize to YYYY-MM. No day/month is invented. Unlabeled
single education dates remain unassigned, while an explicit graduation/completion
label can establish an end date. Work dates require an explicit range. No duration,
chronology correction, experience-years calculation, or fuzzy locale date parsing
is implemented. Certification date has no implied issue/expiry semantics; multiple
dates leave it null.

## Phone safety

`phonenumbers` is the Python port of libphonenumber; see its
[official README](https://github.com/daviddrysdale/python-phonenumbers).

Explicit `+` country codes can normalize without a default country. A national
number needs an explicit supported two-letter `phone_region` (e.g. `GB`, `US`,
`IN`), supplied by the caller rather than inferred from a name, email, locale, or
university. The default is null. Missing-region national numbers retain their
raw value with `status: ambiguous` and `e164: null`. Invalid numbers retain raw
text with `status: invalid`, a null normalized value, and a warning. Extensions
are stored separately. Library validity is numbering-plan validation, not proof
of reachability or ownership. Nothing calls or sends messages to a number.

## Privacy and limitations

Contacts and names are extracted only from introductory/contact sections, to
reduce accidental promotion of references, employers, or project dependencies.
Portfolio links require an explicit website/portfolio label or a github.io host;
LinkedIn/GitHub classification uses actual parsed hosts, not substring matches.
URLs are never fetched. Links do not prove ownership. Name-shaped headers can
still be wrong and receive heuristic provenance/warnings.

English aliases/model/vocabulary are the baseline. Unicode names/scripts are
preserved, with explicit Name labels supported, but language accuracy is not
universal. Column order, omitted headings, commas instead of supported separators,
long headers, unlisted occupations/degrees, multiple roles under one company,
project/certification continuation lines, and unusual institutions can cause missed
or imperfectly split records. Missing fields remain null, and raw blocks remain
available. No accuracy benchmark is claimed.

The application does not log resume text, contact data, source evidence, or model
exception details. Validation responses omit Pydantic `input` and context fields.
Privacy tests cover successful extraction, validation failure, and inference failure.
Do not enable request-body, third-party NLP/parser debug, or response logging on
candidate requests. Existing local-only ingestion limitations still apply: no
authentication, retention service, or hard parser/NLP CPU deadline. No OCR,
skill recognition, matching, database work, frontend dashboard, or deployment
has been added in Phase 3.

Full synthetic input/output: [input](examples/synthetic-resume.txt) and
[JSON output](examples/candidate.sample.json). The output was generated with the
real installed pretrained model; all candidate content is fabricated for testing.
