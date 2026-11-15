# Skill knowledge base and extraction (Phase 4)

The local ontology is `backend/app/data/skills.json`, version **1.0.0**, containing
137 canonical skills in eight categories: technical, programming_languages,
frameworks, databases, cloud_tools, data_science, machine_learning, and soft_skills.
It is a source file intended for review and version control with the application,
not a generated cache or downloaded API response. No paid or external API is used.

## Service and parser integration

`app/services/skills.py` supplies `SkillExtractor` and the cached default
`get_skill_extractor()`. `app/schemas/skills.py` validates the ontology and defines
typed results. `app/services/sections.py` shares the existing heading vocabulary
with the parser and tracks section content offsets without merging positions.

The matcher uses Python's local regex engine with escaped literal aliases,
case-insensitive matching, Unicode-aware delimiter checks, and explicit context
gates. This is the alternative deterministic matching approach permitted by the
phase requirements; it does not require spaCy's pretrained NER model. No runtime
or development dependencies were added. Regex syntax/Unicode behavior follows the
[Python regex documentation](https://docs.python.org/3/library/re.html).

`ResumeParser.parsefile()` and `POST /api/v1/resumes/parse-text` now add:

- `skills`: deduplicated canonical skill records, in first-occurrence order.
- `skill_ontology_version`: the ontology version used for matching.

Existing text, sections, warnings, and metadata fields are preserved. The separate
Phase 3 `/extract` candidate schema is unchanged; skill results come from the
parser, not its NER pipeline. Candidate inference does not run as part of parsing.

For input text `Skills: JS`, the added fields are:

```json
{
  "skill_ontology_version": "1.0.0",
  "skills": [
    {
      "name": "JavaScript",
      "category": "programming_languages",
      "explicitly_listed": true,
      "occurrences": [
        {
          "text": "JS",
          "start": 8,
          "end": 10,
          "alias": "JS",
          "section": "skills",
          "source_type": "explicit",
          "context_rule": null
        }
      ]
    }
  ]
}
```

Offsets are half-open Python character indexes into the parser response's
normalized `text`, so `text[start:end] == occurrence.text`. They are not PDF
coordinates or offsets into the original file bytes. Every occurrence is retained;
one canonical skill may have both explicit-list and experience/project evidence.
No resume text or supporting spans are written to logs or a database.

`source_type` is `explicit` for a recognized Skills heading, `experience` for work
history, `project` for Projects, and `other` for remaining/unclassified text.
`explicitly_listed` is true if any occurrence is in Skills. Headings themselves
are skipped; inline content after `Skills:` is included at its real offset.
Repeated sections and empty sections are handled. The same recognized English
heading aliases are used by parsing and skill attribution; unknown headings do
not reset the current section. Text before a heading is `unclassified` for skill
attribution even though the older section dictionary groups preamble as contact.

## Matching rules

- React/React.js/ReactJS normalize to React, JS to JavaScript, ML to Machine Learning.
- Java is not extracted inside JavaScript; SQL is not extracted inside MySQL.
- Aliases are literal, including `C++`, `C#`, `.NET`, `Node.js`, and `CI/CD`.
- Longer phrases at the same start position win. React Native does not also add
  React, and GitHub Actions does not imply Git. No prerequisite/parent skills are
  inferred from an ontology match.
- Spaces/tabs/Unicode nonbreaking spaces between alias words are accepted within
  a line. Aliases are not joined across line breaks. Unicode candidate text and
  offsets are preserved; this service does not rewrite the input string.
- Identifier, Unicode letter/mark/number, underscore, email, URL, filename, and
  qualified-name boundaries prevent many embedded-token matches.
- Bare R, Go, and C require a clean skill-list entry or local programming evidence.
  For example, `Skills: R, Go` and `Built backend services in Go` match, while
  `go to school`, `R&D`, and `R Smith` do not. Unambiguous alternatives such as
  Golang, R programming, and C language match directly. Mixed/Unicode list
  separators are supported. Arbitrary prose under Skills is not enough.
- Bare React needs technical/list context or a standalone experience/project cell.
  Bare Render has hosting/deployment gating; `render images in Python` does not
  establish knowledge of Render hosting. `React.js` and `Render.com` are clearer
  aliases and do not need that gate.
- ML requires a list or technical context; `5 ml` is not Machine Learning.

## Developer workflow: add or change skills

1. Edit `backend/app/data/skills.json`. Add a canonical record to `skills`:

   ```json
   {
     "name": "Example Framework",
     "category": "frameworks",
     "aliases": ["ExampleFW"]
   }
   ```

   The canonical name always matches automatically. Do not repeat it in aliases
   or add case-only variants. Choose an existing category from `SkillCategory` in
   `app/schemas/skills.py`; adding a category requires updating that type, docs,
   and category coverage tests together.

2. For a genuinely ambiguous alias, list it in `ambiguous_aliases` and select an
   existing rule (`programming_language`, `technical_context`, `machine_learning`):

   ```json
   {
     "name": "Go",
     "category": "programming_languages",
     "aliases": ["Golang", "Go language"],
     "ambiguous_aliases": ["Go"],
     "context_rule": "programming_language"
   }
   ```

   A new ambiguity behavior requires a reviewed rule implementation in
   `skills.py` and positive/negative tests. Do not disable context rules merely
   to force a desired count.

3. Increment the semantic `version` for a reviewed ontology change, normally a
   patch version for alias/skill additions. Treat canonical renames/removals or
   category changes as contract changes. Commit the JSON, code/tests, and relevant
   documentation together through your normal Git review workflow.

4. Validate from the repository root:

   ```powershell
   Push-Location backend
   .venv/Scripts/python.exe -m pytest tests/test_skills.py -q
   .venv/Scripts/python.exe -m pytest -q
   Pop-Location
   ```

   Loader validation rejects unsupported categories, unknown fields, empty names,
   whitespace-only/duplicate aliases, cross-skill collisions, and missing context
   policies. Alias collision checks normalize NFC, case, and spacing. New aliases
   need tests for positive examples, confusing prose, punctuation, and boundaries.

5. Restart backend workers after editing the default ontology. Compiled matching
   configuration is cached per process; no candidate content/results are cached.
   Direct tests can instantiate `SkillExtractor(path_to_test_ontology)` without
   changing production data. The path is resolved relative to source, not CWD.

Direct use from `backend/`:

```python
from app.services.skills import SkillExtractor

skills = SkillExtractor().extract("Technical Skills: ReactJS, JS, Go")
result = [skill.model_dump(mode="json") for skill in skills]
```

Existing installation/run instructions still apply. No new endpoint or API key is
needed; upload a PDF/DOCX through `/parse-text` to receive the new fields. See
[full synthetic parser response](examples/skills.sample.json), generated from a
synthetic DOCX (temporary fixture removed after generation).

## Limits

The ontology is a curated starter vocabulary, not an exhaustive skill catalog.
Unknown aliases, inflections, languages, misspellings, wrapped phrases, and omitted
or unusual section headings can cause misses. Some ordinary words (e.g. Rust,
Spark, Leadership) may still be ambiguous. Context gates trade recall for fewer
false positives; they do not provide complete semantic disambiguation.

A mention, including a negated, desired, or quoted mention, is not evidence of
mastery. Negation, proficiency levels, skill duration, taxonomy inheritance, and
candidate ownership are not inferred. An explicitly listed skill is distinguished
by location, not verified ability. There is no confidence probability, model
training, matching/ranking, persistence, OCR, dashboard, or deployment in Phase 4.
