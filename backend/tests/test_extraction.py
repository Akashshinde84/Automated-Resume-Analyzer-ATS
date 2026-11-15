import pytest

from app.schemas.candidate import NamedEntity, NLPMetadata
from app.services.extraction import InformationExtractor


class StubNER:
    """Deterministic test double, not a custom-trained or pretrained model."""
    def __init__(self, people=(), orgs=()):
        self.people = people
        self.orgs = orgs

    def analyze(self, text):
        entities = []
        for label, values in (("PERSON", self.people), ("ORG", self.orgs)):
            for value in values:
                if value in text:
                    start = text.index(value)
                    entities.append(NamedEntity(text=value, label=label, start=start, end=start + len(value)))
        return entities, NLPMetadata(model="test-double", status="unavailable"), []


@pytest.fixture
def extractor():
    return InformationExtractor(StubNER())


SYNTHETIC = """Name: Jordan Example
jordan@example.test
Phone: +44 20 7946 0018
linkedin.com/in/jordan-example
github.com/jordan-example
Portfolio: https://jordan.example.test
Education
Example University | Bachelor of Science in Computer Science | 2016 - 2020
Experience
Software Engineer | Example Labs | Jan 2021 - Present
- Built internal services.
Projects
Project: Example Analyzer
- Built a synthetic document tool.
Certifications
Certificate: Example Cloud Certificate | Issuer: Example Institute | 2023
"""


def test_full_synthetic_resume(extractor):
    result = extractor.extract(SYNTHETIC)
    candidate = result.candidate
    assert candidate.name == "Jordan Example"
    assert candidate.emails == ["jordan@example.test"]
    assert candidate.phones[0].e164 == "+442079460018"
    assert candidate.linkedin_urls == ["https://linkedin.com/in/jordan-example"]
    assert candidate.github_urls == ["https://github.com/jordan-example"]
    assert candidate.portfolio_urls == ["https://jordan.example.test"]
    education = candidate.education[0]
    assert (education.institution, education.degree, education.field) == ("Example University", "Bachelor of Science", "Computer Science")
    assert (education.start_date, education.end_date) == ("2016", "2020")
    experience = candidate.work_experience[0]
    assert (experience.company, experience.job_title) == ("Example Labs", "Software Engineer")
    assert (experience.start_date, experience.end_date) == ("2021-01", "present")
    assert experience.description == "- Built internal services."
    assert candidate.projects[0].name == "Example Analyzer"
    assert candidate.certifications[0].issuer == "Example Institute"
    assert candidate.certifications[0].date == "2023"
    assert education.provenance
    assert result.nlp.custom_trained is False
    assert 'jordan@example.test' in result.model_dump_json()


def test_missing_fields_stay_empty(extractor):
    result = extractor.extract("Summary\nEnthusiastic professional.")
    assert result.candidate.name is None
    assert result.candidate.emails == []
    assert result.candidate.phones == []
    assert result.candidate.work_experience == []
    assert result.candidate.education == []


@pytest.mark.parametrize("name", ["José García", "李明", "अदिति शर्मा", "علي حسن", "Zoë O’Neil", "Ma Li"])
def test_explicit_unicode_names(extractor, name):
    assert extractor.extract(f"Name: {name}\nEducation\nExample University").candidate.name == name


def test_header_heuristic_and_person_baseline():
    text = "Jane Doe\njane@example.test\nExperience\nWorked with Alan Turing at Example Labs."
    result = InformationExtractor(StubNER(people=["Jane Doe", "Alan Turing"], orgs=["Example Labs"])).extract(text)
    assert result.candidate.name == "Jane Doe"
    assert result.candidate.provenance[-1].method == "pretrained_ner"
    assert result.candidate.provenance[-1].confidence is None


def test_ambiguous_entities_not_promoted_to_candidate_name():
    result = InformationExtractor(StubNER(orgs=["Example Research"])).extract("Example Research\ncontact@example.test")
    assert result.candidate.name is None
    assert any("ambiguous" in warning for warning in result.warnings)
    result = InformationExtractor(StubNER(people=["Alan Turing"])).extract("Experience\nWorked with Alan Turing.")
    assert result.candidate.name is None


def test_multiple_experiences_without_blank_lines(extractor):
    result = extractor.extract("""Experience
Example Labs
Senior Engineer
Jan 2022 - Present
- Built services.
Other Systems
Software Developer
06/2019 - 12/2021
- Maintained applications.
""")
    jobs = result.candidate.work_experience
    assert len(jobs) == 2
    assert [(j.company, j.job_title) for j in jobs] == [("Example Labs", "Senior Engineer"), ("Other Systems", "Software Developer")]
    assert jobs[0].description == "- Built services."
    assert jobs[1].start_date == "2019-06"
    assert jobs[1].end_date == "2021-12"


def test_title_first_and_ner_company():
    result = InformationExtractor(StubNER(orgs=["OpenAI"])).extract("Experience\nResearch Engineer\nOpenAI\n2020–2022\n- Built tools.")
    record = result.candidate.work_experience[0]
    assert record.company == "OpenAI"
    assert record.job_title == "Research Engineer"
    assert any(p.method == "pretrained_ner" for p in record.provenance)


def test_unknown_company_and_title_are_not_invented(extractor):
    record = extractor.extract("Experience\nFreelance activities\n2021 - 2022\n- Created tools.").candidate.work_experience[0]
    assert record.company is None
    assert record.job_title is None
    assert "Freelance activities" in record.description


def test_multiple_education_degree_first(extractor):
    records = extractor.extract("""Education
BSc in Computer Science
Example University
2015 - 2019
Master of Science in Data Science
Other Institute
2020 - 2022
""").candidate.education
    assert len(records) == 2
    assert records[0].institution == "Example University"
    assert records[0].degree == "BSc"
    assert records[1].field == "Data Science"
    assert records[1].institution == "Other Institute"


def test_degree_is_not_assumed_from_org_ner():
    result = InformationExtractor(StubNER(orgs=["BSc", "Example University"])).extract("Education\nExample University\nBSc in Physics")
    assert result.candidate.education[0].degree == "BSc"
    assert next(p for p in result.candidate.education[0].provenance if p.field == "degree").method == "heuristic"
    result = InformationExtractor(StubNER(orgs=["Unknown Award"])).extract("Education\nUnknown Award")
    assert result.candidate.education[0].degree is None
    assert result.candidate.education[0].institution is None


def test_single_education_date_is_flagged(extractor):
    record = extractor.extract("Education\nExample University | BA in History | 2020").candidate.education[0]
    assert record.start_date is None
    assert record.end_date is None
    assert record.warnings


def test_projects_and_certificates(extractor):
    result = extractor.extract("""Projects
Project: Atlas
- Built maps.
https://github.com/example/atlas
Project: Beacon
- Created alerts.
Certifications
Certificate: Example Award | Issuer: Example Board | 2022
Certificate: Other Award
Credential ID: SYNTHETIC-123
""")
    assert [p.name for p in result.candidate.projects] == ["Atlas", "Beacon"]
    assert result.candidate.projects[0].urls == ["https://github.com/example/atlas"]
    assert len(result.candidate.certifications) == 2
    assert result.candidate.certifications[1].issuer is None
    assert result.candidate.certifications[1].credential_id == "SYNTHETIC-123"


def test_references_not_used_as_candidate_contacts(extractor):
    result = extractor.extract("Name: Jane Doe\nEducation\nExample University\nreference@example.test\n+1 650 253 0000")
    assert result.candidate.emails == []
    assert result.candidate.phones == []


def test_empty_input(extractor):
    result = extractor.extract("")
    assert result.candidate.name is None
    assert result.candidate.education == []
    assert any("No text" in w for w in result.warnings)


def test_explicit_graduation_date(extractor):
    record = extractor.extract("Education\nExample University | BSc Computer Science\nGraduated 2020").candidate.education[0]
    assert record.end_date == "2020"
    assert record.field == "Computer Science"


def test_multiple_orgs_in_header_leave_company_null():
    result = InformationExtractor(StubNER(orgs=["OpenAI", "Microsoft"])).extract("Experience\nEngineer | OpenAI | Microsoft | 2020 - 2022\n- Built tools.")
    assert result.candidate.work_experience[0].company is None


@pytest.mark.parametrize("degree", ["B.S.", "M.S.", "B.A.", "M.A.", "Bachelor’s", "Master’s"])
def test_additional_degree_formats(extractor, degree):
    record = extractor.extract(f"Education\nLondon School of Economics\n{degree} in Economics").candidate.education[0]
    assert record.institution == "London School of Economics"
    assert record.degree
    assert record.field == "Economics"
