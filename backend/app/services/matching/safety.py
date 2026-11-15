"""Conservative text/evidence gates shared by resume and job processing."""
from dataclasses import dataclass
import re

from app.services.sections import iter_section_lines

# Drop mixed personal/technical clauses rather than let personal criteria affect scores.
PERSONAL = re.compile(r"\b(?:name\s*:|age\s*[:=]|aged\s+\d|\d+\s*(?:years? old|year-old)|gender|sex\s*:|pronouns?|date of birth|DOB\b|born\b|religion|religious|race\s*:|ethnic(?:ity)?|nationality|citizenship|marital|pregnan\w*|disabilit\w*|sexual orientation|male|female|men only|women only|young|older|national origin|address\s*:|salary|compensation|equal opportunity)(?=\s|$|[^\w])", re.I)
INSTRUCTION = re.compile(r"\b(?:ignore (?:all|previous|prior)|system prompt|system message|override|(?:set|return|give|output|assign) (?:the )?(?:overall )?score|hire (?:me|this)|reject (?:all|this)|hiring decision)\b", re.I)
NEGATION = re.compile(r"\b(?:no|not|without|lack|lacks|lacking|never|don't|do not|cannot)\b", re.I)
ASPIRATION = re.compile(r"\b(?:learning|studying|plan to|want to|aspire|interested in|hoping to)\b", re.I)
SAFE_RESUME_SECTIONS = {"skills", "summary", "experience", "projects", "certifications"}


@dataclass(frozen=True)
class Unit:
    text: str
    start: int
    section: str
    importance: str = "unspecified"


def blocked(text):
    return bool(PERSONAL.search(text) or INSTRUCTION.search(text))


def affirmative(text, start, end, resume=False):
    # Keep scope after the last comma. Shared "no Python or Java" suppresses both.
    prefix = text[:start].rsplit(",", 1)[-1]
    suffix = text[end:]
    if NEGATION.search(prefix) or re.match(r"\s+(?:is )?not (?:required|needed|necessary|used|known)\b", suffix, re.I):
        return False
    return not (resume and ASPIRATION.search(prefix))


def resume_units(text):
    units = []
    excluded = False
    for line in iter_section_lines(text):
        if line.section not in SAFE_RESUME_SECTIONS:
            continue
        # Clauses let a skills statement survive a separate negated statement.
        for match in re.finditer(r"[^;]+", line.text):
            if blocked(match.group()):
                excluded = True
                continue
            units.append(Unit(match.group(), line.start + match.start(), line.section))
    return units, excluded
