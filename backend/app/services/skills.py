"""Local ontology matcher with Unicode boundaries and auditable context gates."""
from functools import lru_cache
from pathlib import Path
import re
import unicodedata

from app.schemas.skills import DetectedSkill, SkillOntology, SkillSpan, alias_key
from app.services.sections import iter_section_lines

ONTOLOGY_PATH = Path(__file__).resolve().parents[1] / "data" / "skills.json"
# Ignore skills embedded in a URL or email rather than asserting candidate ability.
PROTECTED = re.compile(r"(?:https?://|www\.)\S+|[\w.+-]+@[\w.-]+\.[\w-]+", re.I)
TECHNICAL = re.compile(r"\b(?:programming|language|developer|engineer|software|backend|frontend|front-end|web|app|apps|application|applications|API|APIs|services|microservices|code|coding|data|analysis|analytics|statistical|statistics|model|models|scripts|framework|library|JavaScript|TypeScript|Python|SQL|deployment|deploy|deployed|hosting|cloud)\b", re.I)


def _word(character):
    return bool(character) and (character == "_" or unicodedata.category(character)[0] in "LMN")


def _boundaries(text, start, end):
    before = text[start - 1] if start else ""
    after = text[end] if end < len(text) else ""
    if _word(before) or _word(after) or before in {"+", "#"} or after in {"+", "#"}:
        return False
    # Do not match fragments in qualified identifiers, filenames or bare domains.
    if before == "." and start > 1 and _word(text[start - 2]):
        return False
    if after == "." and end + 1 < len(text) and _word(text[end + 1]):
        return False
    return True


def _listed(line, start, end, section):
    if section != "skills":
        return False
    # A skills heading does not make arbitrary prose like 'go to market' a skill.
    left = re.split(r"[,;|/\u2022\u3001\uff0c\uff1b]", line[:start])[-1].strip(" -\t")
    right = re.split(r"[,;|/\u2022\u3001\uff0c\uff1b]", line[end:])[0].strip()
    left = re.sub(r"^(?:languages?|programming languages?|frameworks?|tools?|skills?|proficient in|databases?)\s*:\s*", "", left, flags=re.I)
    return not left and bool(re.fullmatch(r"(?:\((?:advanced|intermediate|beginner|basic|expert|\d+\+? years?)\)|[-:]\s*(?:advanced|intermediate|beginner|basic|expert))?\.?", right, re.I))


def _context_allowed(rule, skill, line, start, end, section):
    before, after = line[:start], line[end:]
    if skill.name == "R" and (re.search(r"&\s*D\b", after, re.I) or re.search(r"\bD\s*&\s*$", before, re.I)):
        return False
    if rule == "machine_learning" and re.search(r"\d\s*$", before):
        return False  # e.g. 5 ml, a volume rather than Machine Learning.
    if _listed(line, start, end, section):
        return True
    if rule == "programming_language":
        prefix = re.search(r"\b(?:in|using|with|programming|language|proficient in|experience with)\s*$", before, re.I)
        suffix = re.match(r"\s+(?:(?:is (?:a )?)?programming language|language|developer|development|packages|scripts|services|microservices)\b", after, re.I)
        if skill.name == "R" and re.search(r"\b(?:RStudio|tidyverse|ggplot2|rstats)\b", line, re.I):
            return True
        return bool(suffix or (prefix and TECHNICAL.search(before + after)))
    if rule == "technical_context":
        if skill.name == "Render":
            return bool(re.search(r"\b(?:to|on|using)\s*$", before, re.I) and re.search(r"\b(?:deploy|deployed|hosting|hosted|service|app)\b", line, re.I))
        if section in {"experience", "projects"} and not (before + after).strip():
            return True
        if skill.name == "React" and re.search(r"\b(?:using|with)\s*$", before, re.I):
            return True
        return bool(TECHNICAL.search(before + after))
    if rule == "machine_learning":
        return bool(TECHNICAL.search(before + after) or re.match(r"\s+(?:pipelines?|algorithms?|training|inference|engineering)\b", after, re.I))
    return False


class SkillExtractor:
    def __init__(self, ontology_path: str | Path = ONTOLOGY_PATH):
        self.ontology = SkillOntology.model_validate_json(Path(ontology_path).read_text(encoding="utf-8-sig"))
        definitions = []
        for skill in self.ontology.skills:
            for alias in (skill.name, *skill.aliases):
                definitions.append((skill, alias))
        # Longest phrase at a position wins: React Native does not also imply React.
        definitions.sort(key=lambda entry: (-len(entry[1]), alias_key(entry[1])))
        self._aliases = {f"a{index}": definition for index, definition in enumerate(definitions)}
        patterns = []
        for group, (_, alias) in self._aliases.items():
            pattern = r"[^\S\r\n]+".join(re.escape(word) for word in alias.split())
            patterns.append(f"(?P<{group}>{pattern})")
        self._pattern = re.compile(r"(?<!\w)(?:" + "|".join(patterns) + r")(?!\w)", re.I)

    def extract(self, text: str) -> list[DetectedSkill]:
        """Offsets index the supplied string exactly; input is never rewritten."""
        if not isinstance(text, str):
            raise TypeError("Skill extraction requires text.")
        detected = {}
        for line in iter_section_lines(text):
            protected = list(PROTECTED.finditer(line.text))
            for match in self._pattern.finditer(line.text):
                start, end = match.span()
                if not _boundaries(line.text, start, end):
                    continue
                if any(start < p.end() and p.start() < end for p in protected):
                    continue
                skill, alias = self._aliases[match.lastgroup]
                rule = skill.context_rule if alias_key(alias) in {alias_key(a) for a in skill.ambiguous_aliases} else None
                if rule and not _context_allowed(rule, skill, line.text, start, end, line.section):
                    continue
                source = {"skills": "explicit", "experience": "experience", "projects": "project"}.get(line.section, "other")
                occurrence = SkillSpan(text=match.group(), start=line.start + start, end=line.start + end,
                                       alias=alias, section=line.section, source_type=source, context_rule=rule)
                if skill.name not in detected:
                    detected[skill.name] = DetectedSkill(name=skill.name, category=skill.category)
                record = detected[skill.name]
                record.explicitly_listed |= source == "explicit"
                record.occurrences.append(occurrence)
        return list(detected.values())


@lru_cache(maxsize=1)
def get_skill_extractor() -> SkillExtractor:
    """Immutable matching configuration is reused; per-resume output is never cached."""
    return SkillExtractor()
