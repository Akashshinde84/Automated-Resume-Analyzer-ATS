"""Candidate name selection is restricted to introductory/contact lines."""
import re
import unicodedata

from app.services.extraction.contacts import evidence
from app.services.extraction.records import COMPANY, TITLE, UNIVERSITY
from app.services.parser import ALIASES

EXCLUDED = {"resume", "curriculum vitae", "cv", "contact", "contact information", "personal details"}


def plausible(value):
    value = re.sub(r"^(?:dr|mr|ms|mrs)\.?\s+", "", value, flags=re.I).strip()
    if not value or len(value) > 80 or any(c.isdigit() for c in value):
        return False
    if any(c in value for c in "@:/|<>[]") or TITLE.search(value) or COMPANY.search(value) or UNIVERSITY.search(value) or re.search(r"\b(?:bachelor|master|diploma|doctorate)\b", value, re.I):
        return False
    tokens = value.split()
    if not 1 <= len(tokens) <= 5:
        return False
    return all(c.isalpha() or c in " .'-’" or unicodedata.category(c).startswith("M") for c in value)


def extract_name(contact, entities):
    lines = [line for line in contact.splitlines() if line.strip()]
    for line in lines[:8]:
        match = re.match(r"(?:candidate name|full name|name)\s*:\s*(.+)", line, re.I)
        if match and plausible(match[1]):
            return match[1], [evidence("name", "heuristic", "explicit_name_label", line, "high")], []
    for line in lines[:5]:
        if line.casefold().strip(": ") in EXCLUDED | set(ALIASES):
            continue
        if not plausible(line):
            # Never search work/education content for a different PERSON.
            continue
        people = {entity.text for entity in entities if entity.label == "PERSON" and entity.text in line}
        orgs = {entity.text for entity in entities if entity.label == "ORG" and entity.text in line}
        if len(people) > 1 or orgs:
            return None, [], ["Candidate name is ambiguous in the introductory text; name remains null."]
        if len(people) == 1 and next(iter(people)) == line:
            return line, [evidence("name", "pretrained_ner", "person_in_introductory_header", line, None)], []
        tokens = line.split()
        if 2 <= len(tokens) <= 5 and all(token[0].isupper() for token in tokens):
            return line, [evidence("name", "heuristic", "name_shaped_introductory_line", line, "low")], [
                "Candidate name uses an introductory-line heuristic; verify it."
            ]
        if len(tokens) == 1 and 2 <= len(line) <= 8 and all(ord(c) > 127 and c.isalpha() for c in line):
            return line, [evidence("name", "heuristic", "single_non_latin_introductory_name", line, "low")], [
                "Candidate name uses an introductory-line heuristic; verify it."
            ]
    return None, [], []
