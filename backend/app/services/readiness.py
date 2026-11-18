"""Deterministic resume readiness rubric. No external calls or inferred facts."""
import re
import unicodedata

from app.schemas.readiness import (
    Improvement, ReadinessCategory, ReadinessCheck, ReadinessResult, ReadinessWeights,
)
from app.services.document_links import normalize_url
from app.services.matching.safety import affirmative, blocked

ACTION = re.compile(r"^(?:built|developed|designed|implemented|created|led|improved|reduced|increased|automated|delivered|deployed|organized|analysed|analyzed|optimized|integrated|tested|maintained|launched|managed|supported|resolved|researched)\b", re.I)
METRIC = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|percent\b|users?\b|requests?\b|records?\b|customers?\b|hours?\b|minutes?\b|seconds?\b|milliseconds?\b|ms\b|tests?\b|projects?\b|students?\b|participants?\b|reports?\b|endpoints?\b|teams?\b|x\b)", re.I)
GENERIC = re.compile(r"\b(?:hard.?working|team player|results.?driven|self.?motivated|go.?getter)\b", re.I)


class ReadinessService:
    def __init__(self, weights=None):
        self.weights = weights or ReadinessWeights()

    def evaluate(self, parsed, extraction):
        candidate = extraction.candidate
        text = parsed.text
        sections = parsed.sections
        categories, recommendations, strengths = [], [], []
        present = bool(text.strip())
        records = [*candidate.projects, *candidate.work_experience]
        # Personal/instruction-like clauses are excluded, never demographic features.
        descriptions = ["\n".join(line for line in (record.description or "").splitlines() if not blocked(line)) for record in records]
        lines = [line.lstrip("-• ").strip() for description in descriptions for line in description.splitlines() if line.strip()]
        denominator = max(1, len(records))
        skills = []
        for skill in parsed.skills:
            valid = []
            for occurrence in skill.occurrences:
                start = text.rfind("\n", 0, occurrence.start) + 1
                end = text.find("\n", occurrence.end)
                line = text[start:end if end >= 0 else len(text)]
                if occurrence.section in {"skills", "projects", "experience", "summary", "certifications"} and not blocked(line) and affirmative(line, occurrence.start-start, occurrence.end-start, resume=True):
                    valid.append(occurrence)
            if valid:
                skills.append((skill.name, valid))

        def category(key, label, rules):
            maximum = getattr(self.weights, key)
            total = sum(rule[2] for rule in rules)
            checks = []
            for code, title, base, ratio, evidence, suggestion, priority, section in rules:
                evidence = [value[:240] for value in evidence[:3]]
                available = maximum * base / total
                earned = available * min(1, max(0, ratio)) if present else 0
                checks.append(ReadinessCheck(code=code, label=title, earned=round(earned, 4), maximum=round(available, 4),
                    reason=f"{ratio:.0%} of this rule's criterion observed." if present else "No readable text; this rule cannot be assessed.", evidence=evidence[:3]))
                if present and ratio < 1 and maximum:
                    recommendations.append(Improvement(code=code, priority=priority, problem=title + " is incomplete or unclear.",
                        why=label + " helps readers locate and interpret your existing qualifications.", section=section,
                        suggestion=suggestion, possible_points=round(available-earned, 2), evidence=evidence[:3]))
                elif present and ratio >= 1 and maximum:
                    strengths.append(title)
            score = round(maximum * sum(rule[2] * min(1, max(0, rule[3])) for rule in rules) / total, 2) if present else 0
            categories.append(ReadinessCategory(key=key, label=label, score=score, maximum=maximum, checks=checks))

        contact = bool(candidate.emails or any(phone.status == "valid" for phone in candidate.phones))
        all_links = [*candidate.linkedin_urls, *candidate.github_urls, *candidate.portfolio_urls,
                     *(url for project in candidate.projects for url in project.urls)]
        category("contact", "Contact information and valid links", [
            ("reachable_contact", "A readable email or valid phone number", 8, float(contact),
             ["Email detected" if candidate.emails else "Valid phone detected"] if contact else [],
             "Add an email address or a valid phone number in readable text. A social profile is optional.", "high", "contact"),
            ("link_syntax", "Supplied links have valid URL syntax", 2, float(all(normalize_url(url) for url in all_links)),
             [f"{len(all_links)} supplied links checked for syntax; website availability was not tested."],
             "Correct the syntax of any supplied URL. No social link is required; verify destinations yourself.", "medium", "contact / projects"),
        ])
        category("structure", "Resume structure and section organization", [
            ("skills_heading", "A recognizable Skills section", 5, float(bool(sections.get("skills"))), [], "Use a Skills heading followed by an accurate skills list.", "medium", "skills"),
            ("education_heading", "A recognizable qualification section", 5, float(bool(sections.get("education") or sections.get("certifications"))), [], "Use Education or Certifications headings for qualifications you actually hold.", "medium", "education / certifications"),
            ("work_heading", "A recognizable Projects or Experience section", 10, float(bool(sections.get("projects") or sections.get("experience"))), [], "Use Projects for academic/personal work or Experience for employment. Employment history is not required.", "high", "projects / experience"),
        ])
        category("skills", "Skills presentation", [
            ("skills_found", "Recognized affirmative skill evidence", 5, float(bool(skills)), [name for name, _ in skills[:3]], "Name the tools and skills you actually used. The supported skill ontology is limited.", "medium", "skills"),
            ("skills_listed", "Skills presented explicitly", 5, float(any(any(o.section == "skills" for o in spans) for _, spans in skills)), [], "List supported skills under Skills, without claiming unearned proficiency.", "medium", "skills"),
            ("skills_applied", "Skills connected to projects or experience", 5, float(any(any(o.section in {"projects", "experience"} for o in spans) for _, spans in skills)), [], "Explain where you used a listed skill in an actual project or role.", "medium", "projects / experience"),
        ])
        titles = [record.name if hasattr(record, "name") else record.job_title for record in records]
        described = sum(len(re.findall(r"\b\w+\b", description)) >= 8 for description in descriptions) / denominator
        action_records = sum(any(ACTION.search(line.lstrip("-• ")) for line in description.splitlines()) for description in descriptions) / denominator
        category("descriptions", "Project and experience descriptions", [
            ("record_titles", "Identifiable project or role titles", 5, sum(bool(title) for title in titles)/denominator, [title for title in titles if title][:3], "Give each real project or role a clear title.", "medium", "projects / experience"),
            ("record_detail", "Descriptions with at least eight words per record", 10, described, descriptions[:3], "Explain the problem, your contribution, tools, and outcome using factual details. Eight words is a minimum rubric heuristic, not a writing target.", "high", "projects / experience"),
            ("record_action", "Action-oriented descriptions per record", 5, action_records, lines[:3], "Start a contribution with an accurate action verb such as Built, Designed, Analyzed, or Organized.", "medium", "projects / experience"),
        ])
        qualifications = [*candidate.education, *candidate.certifications]
        complete = any(record.institution and record.degree for record in candidate.education) or any(record.name and record.issuer for record in candidate.certifications)
        category("qualifications", "Education and qualifications", [
            ("qualification_found", "A recorded qualification", 5, float(bool(qualifications)), [], "Add your actual education or relevant certification. No particular institution or degree level is preferred.", "medium", "education / certifications"),
            ("qualification_detail", "Qualification and provider identified", 5, float(complete), [record.raw_text[:180] for record in qualifications[:2]], "State the qualification and institution, or certification and issuer. Leave unknown facts unclaimed.", "medium", "education / certifications"),
        ])
        readable = sum(unicodedata.category(character)[0] in "LMNPZS" or character.isspace() for character in text) / max(1, len(text))
        extraction_issues = any("two-column" in warning.lower() or "unresolved" in warning.lower() for warning in parsed.warnings)
        image_pages = parsed.metadata.image_only_pages or []
        category("readability", "ATS text readability and parsing quality", [
            ("text_present", "Extractable document text", 5, float(present), [f"{len(text)} extracted characters"], "Export a text-based PDF or DOCX; OCR is unavailable.", "high", "document"),
            ("text_quality", "At least 95% readable characters", 5, float(readable >= .95 and "\ufffd" not in text), [f"Readable character ratio: {readable:.1%}"], "Review copied/extracted text for broken characters and export again if needed.", "high", "document"),
            ("layout_quality", "No detected image-only or ambiguous layout issues", 5, float(not image_pages and not extraction_issues), parsed.warnings[:3], "Review reading order and hyperlinks. A simple single-column export may help; file extension alone does not determine compatibility.", "high", "document"),
        ])
        normalized = [re.sub(r"\s+", " ", line).casefold() for line in lines]
        unique_ratio = len(set(normalized)) / max(1, len(normalized))
        measured = [line for line in lines if any(affirmative(line, match.start(), match.end(), resume=True) for match in METRIC.finditer(line))]
        category("clarity", "Clarity and evidenced achievements", [
            ("clarity_action", "At least one clear contribution", 4, float(any(ACTION.search(line) for line in lines)), lines[:2], "Replace vague responsibility statements with what you actually did.", "low", "projects / experience"),
            ("measured_outcome", "A measurable detail in a description", 4, float(bool(measured)), measured[:2], "Where you have evidence, state scale, time, quantity, or a measured result. Never invent numbers; qualitative outcomes are still useful.", "low", "projects / experience"),
            ("unique_descriptions", "Descriptions without exact repeated lines", 2, unique_ratio if lines else 0, [], "Remove exact repeated contribution lines and use the space for distinct factual details.", "low", "projects / experience"),
        ])
        if not present:
            recommendations = [Improvement(code="no_text", priority="high", problem="No extractable text was found.", why="The resume cannot be assessed without readable text.", section="document", suggestion="Upload a text-based PDF or DOCX. OCR is not available; no readiness score has been assigned.")]
            strengths = []
        else:
            if any(GENERIC.search(line) for line in sections.get("summary", "").splitlines() if not blocked(line)):
                recommendations.append(Improvement(code="generic_summary", priority="low", problem="Generic wording in the summary.", why="Specific contributions communicate more than broad self-descriptions.", section="summary", suggestion="Replace generic phrases with a concise, truthful example of your work."))
            for index, project in enumerate(candidate.projects):
                if project.extraction_warnings:
                    recommendations.append(Improvement(code=f"project_links_{index}", priority="medium", problem="Project link association needs review.", why="Readers need the correct repository or demo for this project.", section="projects", suggestion="Review the original link anchors and make each label unambiguous. No primary URL was guessed.", evidence=project.extraction_warnings[:2]))
                elif "github" in project.raw_text.lower() and not project.github_url:
                    recommendations.append(Improvement(code=f"missing_project_link_{index}", priority="medium", problem="A GitHub label has no resolved repository URL.", why="The label alone does not supply a clickable destination.", section="projects", suggestion="Check the original hyperlink and export with working link annotations. A repository is optional; do not invent one."))
        recommendations.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}[item.priority])
        return ReadinessResult(status="computed" if present else "insufficient_text",
            score=round(sum(category.score for category in categories), 2) if present else None,
            categories=categories, strengths=strengths, recommendations=recommendations,
            limitations=[
                "This document-quality rubric is independent of the Job Match Score and has not been calibrated against employer ATS systems.",
                "Projects and professional roles are interchangeable evidence sources; absence of employment carries no separate penalty.",
                "Social links are optional. Supplied URLs are syntax-checked only; no website availability or ownership check is performed.",
                "Names, age, gender, location, institution prestige and other personal attributes are not scoring features.",
                "Extraction and English action/metric heuristics are incomplete; multilingual or unrecognized evidence can be missed. Empty text produces no score.",
                "Suggested point gains are per-rule upper bounds, not guaranteed improvements; they are not predictions of hiring outcomes.",
            ])
