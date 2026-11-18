# Explainable ATS readiness, rubric 1.0.0

Readiness is a project-defined document-quality estimate, not an official ATS
score, hiring probability or employer prediction. It requires no job description.
The existing Job Match Score remains a separate lexical comparison. Neither
engine infers qualifications or makes hiring decisions.

## Exact formula

For each category, multiply its configured maximum by the sum of earned base
points divided by the sum of available base points. Round each category to two
decimals, then sum those rounded values and round the total to two decimals.
Binary criteria earn all or none of their base points. Ratios below earn the
stated fraction. No readable text means `score: null`, `status: insufficient_text`;
zero-filled category placeholders do not constitute an assigned score.

| Category | Default maximum | Base criteria within the category |
| --- | ---: | --- |
| Contact and links | 10 | 8: at least one extracted email or valid phone; 2: all supplied HTTP(S) links pass syntax validation. No supplied social links passes the link criterion. |
| Structure | 20 | 5: nonempty Skills section; 5: nonempty Education or Certifications section; 10: nonempty Projects or Experience section. |
| Skills | 15 | 5: at least one supported affirmative skill; 5: at least one in Skills; 5: at least one connected to Projects or Experience. |
| Descriptions | 20 | 5 times fraction of project/role records with a title; 10 times fraction with at least eight description words; 5 times fraction with an action-led description line. With no records all three ratios are zero. |
| Qualifications | 10 | 5: at least one education/certification record; 5: at least one institution+qualification or issuer+certification pair. No prestige, grades or degree-level ranking. |
| Readability | 15 | 5: extractable text; 5: at least 95% Unicode letter/mark/number/punctuation/separator/symbol or whitespace characters, with no replacement character; 5: no detected image-only pages, two-column reading-order warning or unresolved link/layout warning. |
| Clarity | 10 | 4: at least one action-led project/role description line; 4: at least one affirmative measurable detail there; 2 times fraction of distinct description lines (case/whitespace normalized). No lines earns zero. |

The eight-word threshold and readable-character ratio are transparent heuristics,
not a claim of linguistic or ATS correctness. Projects and employment roles use
the same criteria. Adding a job is not necessary for full readiness points.

Action-led lines use an explicit English vocabulary (case insensitive): Built,
Developed, Designed, Implemented, Created, Led, Improved, Reduced, Increased,
Automated, Delivered, Deployed, Organized, Analysed, Analyzed, Optimized,
Integrated, Tested, Maintained, Launched, Managed, Supported, Resolved, Researched.
Leading bullets are removed. This vocabulary is incomplete for other languages.

Measurable details require a number followed by %, percent, users, requests,
records, customers, hours, minutes, seconds, milliseconds/ms, tests, projects,
students, participants, reports, endpoints, teams, or x. Singular/plural forms
are supported. Dates alone are not measurable achievements. Negated and
aspirational claims are excluded with the existing evidence gates. Detection
means a claim appears in the resume; its truth has not been independently verified.

Skills use the existing ontology and affirmation rules in recognized professional
sections. Names and personal attributes are not skill/clarity features. Recognized
skills indicate mentions, not verified proficiency. Unknown ontology skills can
be missed. Contact checks assess presence, not the identity or spelling of names.

## Configuration and recommendations

`READINESS_WEIGHTS` accepts JSON category maximums totaling exactly 100. For example:

```dotenv
READINESS_WEIGHTS={"contact":10,"structure":20,"skills":15,"descriptions":20,"qualifications":10,"readability":15,"clarity":10}
```

Invalid totals, extra keys and negative values fail configuration validation.
Zero-weight categories contribute no points or score-related recommendations.
Criteria remain the same when weights change. The response includes maxima,
each criterion, earned points, observations, strengths, priorities and suggestions.
High priority covers contact, extraction, work-section and description detail;
medium covers organization, supporting skills and qualifications; low covers
clarity and measurable evidence. Additional unscored suggestions flag generic
summary language and unresolved project links.

Each score-related recommendation's `possible_points` is that criterion's current
deficit, an upper bound if fully satisfied. These are not guaranteed gains and
should not be summed as promises. Unsupported metrics, experience, skills and
credentials must never be added just to earn points. Qualitative outcomes remain
useful. Missing employment and optional social links incur no separate penalty.

## Extraction and link uncertainty

Projects retain `urls`, `raw_text`, `provenance`, and `warnings` for compatibility,
and add `github_url`, `live_url`, `evidence`, `extraction_warnings`. A single
evidenced github.com repository URL is the primary repository. Multiple
repositories remain in `urls` with a null primary and an uncertainty warning.
Live URLs require a Demo/Live/Website label; an arbitrary documentation site is
not relabeled as a demo. Technology names are not converted into URLs.

PDF annotations intersecting one text block use that block's position. Those
intersecting several blocks are retained as ambiguous document hyperlinks and
not assigned arbitrarily to a project. DOCX relationships use paragraph anchors.
Labels without destinations are not links. URLs are never fetched, so availability,
ownership, redirects and broken remote destinations are not verified. These
limits avoid sending resume-derived links to third parties or introducing SSRF.
Project boundaries remain heuristic; review source text for unconventional layouts.

## API, reports and persistence

`POST /api/v1/resumes/analyze` returns `readiness` alongside `parsed` and
`extraction`. Readiness is computed before signing a snapshot, and its complete
contents are covered by the integrity receipt. JSON includes all criteria and
evidence; PDF includes the score, seven-category breakdown, strengths and up to
12 recommendations, with remaining detail in JSON. The PDF avoids repeated
per-skill evidence and previews at most 1,200 job-description characters.

Anonymous operation remains stateless and needs no login/access token popup.
The server's signed report receipt is automatic integrity metadata, not login.
Existing owner-mode stored data requires no migration: readiness is recomputed
from stored extraction with the current rubric/configuration on retrieval. This
means a historical record's readiness can change when the rubric configuration
changes. Earlier already-open snapshots should be reanalyzed after this upgrade.

`POST /api/v1/jobs/match` keeps its configurable skill-overlap/TF-IDF formula,
required/preferred/missing skills and truthful gap suggestions. `supporting_records`
lists project/role records containing matched skill evidence. This evidence list
does not alter either score. Job suggestions have priorities and affected sections;
they do not promise readiness or job-score gains.

## Verification and limitations

Tests cover rubric arithmetic, alternate weights, empty scans, no employment
penalty, optional links, personal-attribute invariance, evidence offsets, real
PDF/DOCX links, repeated GitHub labels, ambiguous annotations, project descriptions,
signed-report tampering and complete anonymous upload/download workflows.

Run `backend/scripts/evaluate_extraction_revision.py` for measured diagnostics on
20 existing labeled fictional profiles (10 PDF, 10 DOCX). This reused small corpus
is not representative validation or an accuracy guarantee. Per-case results and
errors are in `docs/evaluation/extraction_revision_results.json`.

The original private resume remains unavailable. It must be supplied to confirm
its complete project/link extraction. OCR, broader multilingual extraction,
production Linux resource enforcement and live hosting are not established by
Windows local tests. No production deployment is claimed.
