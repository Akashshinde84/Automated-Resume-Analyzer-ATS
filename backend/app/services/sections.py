"""Shared heading vocabulary and offset-preserving section iteration."""
from dataclasses import dataclass
import re

HEADINGS = {
    "contact": ("contact", "contact information", "contact details", "personal information"),
    "summary": ("summary", "professional summary", "profile", "professional profile", "objective", "career objective"),
    "skills": ("skills", "technical skills", "core competencies", "key skills", "skills and expertise"),
    "education": ("education", "academic background", "academic qualifications", "educational qualifications"),
    "experience": ("experience", "work experience", "work history", "employment history", "professional experience", "internships", "internship experience", "employment", "career history"),
    "projects": ("projects", "personal projects", "academic projects", "selected projects"),
    "certifications": ("certifications", "certificates", "licenses and certifications", "certifications and licenses"),
    "activities": ("extra curricular activities", "extracurricular activities", "extra-curricular activities", "activities", "co curricular activities", "co-curricular activities", "leadership and activities", "sports and achievements"),
    "other": ("references", "interests", "hobbies", "languages", "awards", "achievements", "declaration", "publications", "volunteering"),
}
ALIASES = {alias: section for section, aliases in HEADINGS.items() for alias in aliases}


def heading_section(line: str) -> str | None:
    heading = line.partition(":")[0]
    key = re.sub(r"\s+", " ", heading.strip(" -–—|\t")).casefold()
    key = re.sub(r"^\d+[.)]\s+", "", key)
    if re.fullmatch(r"(?:[a-z]\s+){3,}[a-z]", key):
        key = key.replace(" ", "")
    key = re.sub(r"\s*&\s*", " and ", key)
    return ALIASES.get(key)


@dataclass(frozen=True)
class SectionLine:
    text: str
    start: int
    section: str


def iter_section_lines(text: str):
    """Skip heading labels, retaining exact offsets and each repeated section."""
    position = 0
    section = "unclassified"
    for full_line in text.splitlines(keepends=True):
        line = full_line.rstrip("\r\n\u2028\u2029")
        detected = heading_section(line)
        if detected:
            section = detected
            colon = line.find(":")
            if colon >= 0:
                offset = colon + 1
                yield SectionLine(line[offset:], position + offset, section)
        else:
            yield SectionLine(line, position, section)
        position += len(full_line)
