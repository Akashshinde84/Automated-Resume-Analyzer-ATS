"""Public extraction pipeline; the Phase 2 parser contract remains unchanged."""
from app.schemas.candidate import Candidate, ExtractionRequest, ExtractionResult
from app.services.extraction.contacts import extract_contacts
from app.services.extraction.identity import extract_name
from app.services.extraction.ner import SpacyNER
from app.services.extraction.records import (
    activity_records, certification_records, education_records, experience_records, project_records,
)
from app.services.document_links import normalize_url, normalize_document_target
from app.services.extraction.contacts import evidence
from urllib.parse import urlsplit
from app.services.parser import normalize_text, segment_sections
from app.services.extraction.project_links import finalize_project


class InformationExtractor:
    def __init__(self, ner=None):
        self.ner = ner if ner is not None else SpacyNER()

    def extract(self, text: str, phone_region: str | None = None, hyperlinks=None, layout_blocks=None) -> ExtractionResult:
        # Direct Python callers receive the same bounds/region validation as HTTP.
        request = ExtractionRequest(text=text, phone_region=phone_region,
                                    hyperlinks=hyperlinks or [], layout_blocks=layout_blocks or [])
        text = normalize_text(request.text)
        sections, _ = segment_sections(text)
        entities, metadata, warnings = self.ner.analyze(text)
        contact = sections.get("contact", "")
        contacts, phone_warnings = extract_contacts(contact, request.phone_region)
        links = [link.model_dump() if hasattr(link, "model_dump") else link for link in (hyperlinks or [])]
        blocks = [block.model_dump() if hasattr(block, "model_dump") else block for block in (layout_blocks or [])]
        title_hints = [normalize_text(block["text"]) for block in blocks if block.get("bold")]
        for link in links:
            if link.get("ambiguous"):
                continue
            url = normalize_document_target(link.get("url", ""))
            if not url:
                continue
            label = link.get("label", "")
            link_text = "Email: " + url[7:] if url.startswith("mailto:") else "Phone: " + url[4:] if url.startswith("tel:") else label + ": " + url
            extra, _ = extract_contacts(link_text, request.phone_region)
            for field in ("linkedin_urls", "github_urls", "portfolio_urls"):
                for value in extra[field]:
                    anchor = link.get("text_start")
                    if (field == "github_urls" and len(urlsplit(value).path.strip("/").split("/")) > 1
                            and anchor is not None and anchor >= len(contact)):
                        continue  # Project repositories belong to their anchored project, not a profile claim.
                    if value not in contacts[field]:
                        contacts[field].append(value)
                        contacts["provenance"].append(evidence(field, "document_link", link.get("source", "embedded_hyperlink"), label + " -> " + value, "high"))
            for value in extra["emails"]:
                if value not in contacts["emails"]:
                    contacts["emails"].append(value)
                    contacts["provenance"].append(evidence("emails", "document_link", "mailto_annotation", url, "high"))
            for value in extra["phones"]:
                if not any((p.e164 or p.raw) == (value.e164 or value.raw) for p in contacts["phones"]):
                    contacts["phones"].append(value)
                    contacts["provenance"].append(evidence("phones", "document_link", "tel_annotation", url))
        name, name_evidence, name_warnings = extract_name(contact, entities)
        contacts["provenance"].extend(name_evidence)
        candidate = Candidate(
            name=name, **contacts,
            education=education_records(sections.get("education", ""), entities),
            work_experience=experience_records(sections.get("experience", ""), entities),
            projects=project_records(sections.get("projects", ""), title_hints),
            certifications=certification_records(sections.get("certifications", ""), title_hints),
            activities=activity_records(sections.get("activities", "")),
            summary=sections.get("summary") or None,
        )
        # Match link anchors to each actual block, rather than every repeated [GitHub] label.
        for records, section_name in ((candidate.projects, "projects"), (candidate.certifications, "certifications")):
            cursor = text.find(sections.get(section_name, ""))
            for record in records:
                start = text.find(record.raw_text, max(0, cursor))
                if start < 0:
                    continue
                end = start + len(record.raw_text)
                for link in links:
                    if link.get("ambiguous"):
                        record.warnings.append("An embedded link has an ambiguous text anchor; no project assignment was made.")
                        continue
                    anchor = link.get("text_start")
                    if anchor is not None and start <= anchor < end:
                        url = normalize_url(link.get("url", ""))
                        if url and url not in record.urls:
                            record.urls.append(url)
                            record.provenance.append(evidence("urls", "document_link", "anchor_inside_record", link.get("label", "") + " -> " + url, "high"))
                cursor = end
        for project in candidate.projects:
            finalize_project(project)
        warnings = list(warnings) + phone_warnings + name_warnings
        experience_status = "records_detected" if candidate.work_experience else "section_empty" if "experience" in sections else "not_detected"
        if experience_status == "not_detected":
            warnings.append("No recognized work-experience section was detected. This does not establish that the candidate has no experience.")
        elif experience_status == "section_empty":
            warnings.append("The experience heading has no readable records; review the original document.")
        if not text:
            warnings.append("No text supplied; candidate fields are empty.")
        warnings.append("Extraction is evidence-based and incomplete; missing fields remain null. Review results before use.")
        return ExtractionResult(candidate=candidate, entities=entities, nlp=metadata,
                                work_experience_status=experience_status,
                                warnings=list(dict.fromkeys(warnings)))
