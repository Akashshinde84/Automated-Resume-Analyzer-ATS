"""Public extraction pipeline; the Phase 2 parser contract remains unchanged."""
from app.schemas.candidate import Candidate, ExtractionRequest, ExtractionResult
from app.services.extraction.contacts import extract_contacts
from app.services.extraction.identity import extract_name
from app.services.extraction.ner import SpacyNER
from app.services.extraction.records import (
    certification_records, education_records, experience_records, project_records,
)
from app.services.parser import normalize_text, segment_sections


class InformationExtractor:
    def __init__(self, ner=None):
        self.ner = ner if ner is not None else SpacyNER()

    def extract(self, text: str, phone_region: str | None = None) -> ExtractionResult:
        # Direct Python callers receive the same bounds/region validation as HTTP.
        request = ExtractionRequest(text=text, phone_region=phone_region)
        text = normalize_text(request.text)
        sections, _ = segment_sections(text)
        entities, metadata, warnings = self.ner.analyze(text)
        contact = sections.get("contact", "")
        contacts, phone_warnings = extract_contacts(contact, request.phone_region)
        name, name_evidence, name_warnings = extract_name(contact, entities)
        contacts["provenance"].extend(name_evidence)
        candidate = Candidate(
            name=name, **contacts,
            education=education_records(sections.get("education", "")),
            work_experience=experience_records(sections.get("experience", ""), entities),
            projects=project_records(sections.get("projects", "")),
            certifications=certification_records(sections.get("certifications", "")),
        )
        warnings = list(warnings) + phone_warnings + name_warnings
        if not text:
            warnings.append("No text supplied; candidate fields are empty.")
        warnings.append("Extraction is evidence-based and incomplete; missing fields remain null. Review results before use.")
        return ExtractionResult(candidate=candidate, entities=entities, nlp=metadata,
                                warnings=list(dict.fromkeys(warnings)))
