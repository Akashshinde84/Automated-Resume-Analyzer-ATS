"""Heading/clause rules for stated requirement importance, never inferred seniority."""
import re

from app.services.matching.safety import Unit, blocked

REQUIRED = r"(?:required(?: skills| qualifications| experience)?|requirements|must[- ]have(?: skills)?|essential(?: skills)?|mandatory(?: skills)?|minimum qualifications)"
PREFERRED = r"(?:preferred(?: skills| qualifications| experience)?|nice[- ]to[- ]have(?: skills)?|desirable(?: skills)?|bonus(?: skills)?)"
HEADING = re.compile(rf"^\s*[-*•]?\s*(?P<label>{REQUIRED}|{PREFERRED})\b\s*:?(?P<rest>.*)$", re.I)
MARKER = re.compile(rf"\b({REQUIRED}|{PREFERRED})\s*:\s*", re.I)
PREF_WORD = re.compile(r"\b(?:preferred|nice[- ]to[- ]have|bonus|desirable|optional)\b", re.I)
REQ_WORD = re.compile(r"\b(?:required|requires?|must|mandatory|essential)\b", re.I)
RESET = re.compile(r"^\s*(?:responsibilities|duties|about (?:us|the company)|benefits|perks|how to apply|location|salary|equal opportunity|skills|technical skills|experience|projects|summary)\s*:?\s*$", re.I)
IGNORE = re.compile(r"^\s*(?:about us|about the company|benefits|perks|how to apply|location|salary|equal opportunity)\b", re.I)


def _importance(label):
    return "preferred" if re.fullmatch(PREFERRED, label, re.I) else "required"


def job_units(text):
    units, warnings = [], []
    state = "unspecified"
    ignoring = False
    offset = 0
    for full in text.splitlines(keepends=True):
        line = full.rstrip("\r\n")
        if blocked(line):
            warnings.append("Personal, unrelated, or instruction-like job clauses were excluded from scoring.")
            offset += len(full)
            continue
        header = HEADING.match(line)
        if header:
            state = _importance(header["label"])
            ignoring = False
        elif IGNORE.match(line):
            ignoring = True
        elif RESET.match(line):
            state, ignoring = "unspecified", False
        if ignoring:
            offset += len(full)
            continue
        markers = list(MARKER.finditer(line))
        segments = []
        if markers:
            if line[:markers[0].start()].strip(" -*•"):
                segments.append((0, markers[0].start(), state))
            for index, marker in enumerate(markers):
                state = _importance(marker[1])
                segments.append((marker.end(), markers[index + 1].start() if index + 1 < len(markers) else len(line), state))
        elif header:
            segments.append((header.start("rest"), len(line), state))
        else:
            segments.append((0, len(line), state))
        for left, right, importance in segments:
            part = line[left:right]
            separator = r"[^;,]+" if PREF_WORD.search(part) and REQ_WORD.search(part) else r"[^;]+"
            for clause in re.finditer(separator, part):
                value = clause.group()
                local = "preferred" if PREF_WORD.search(value) else "required" if REQ_WORD.search(value) else importance
                units.append(Unit(value, offset + left + clause.start(), "job_description", local))
        offset += len(full)
    return units, list(dict.fromkeys(warnings))
