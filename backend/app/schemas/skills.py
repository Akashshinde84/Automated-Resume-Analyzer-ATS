"""Typed versioned skill ontology and evidence output."""
from typing import Literal
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, model_validator

SkillCategory = Literal[
    "technical", "programming_languages", "frameworks", "databases", "cloud_tools",
    "data_science", "machine_learning", "soft_skills",
]
ContextRule = Literal["programming_language", "technical_context", "machine_learning"]


def alias_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split()).casefold()


class SkillDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1)
    category: SkillCategory
    aliases: tuple[str, ...] = ()
    ambiguous_aliases: tuple[str, ...] = ()
    context_rule: ContextRule | None = None

    @model_validator(mode="after")
    def valid_aliases(self):
        aliases = (self.name, *self.aliases)
        if any(not a.strip() or a != a.strip() or "\n" in a or "\r" in a for a in aliases):
            raise ValueError("Skill names and aliases must be nonempty, trimmed, single-line strings.")
        keys = [alias_key(a) for a in aliases]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate aliases within a skill.")
        if any(alias_key(a) not in keys for a in self.ambiguous_aliases):
            raise ValueError("Ambiguous aliases must also be canonical names or aliases.")
        if bool(self.ambiguous_aliases) != bool(self.context_rule):
            raise ValueError("Ambiguous aliases and context_rule must be specified together.")
        return self


class SkillOntology(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    skills: tuple[SkillDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_aliases(self):
        owners = set()
        for skill in self.skills:
            for alias in (skill.name, *skill.aliases):
                key = alias_key(alias)
                if key in owners:
                    raise ValueError("Skill aliases collide across canonical skills.")
                owners.add(key)
        return self


class SkillSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    alias: str
    section: Literal["unclassified", "contact", "summary", "skills", "education", "experience", "projects", "certifications", "activities", "other"]
    source_type: Literal["explicit", "experience", "project", "other"]
    context_rule: ContextRule | None = None


class DetectedSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    category: SkillCategory
    explicitly_listed: bool = False
    occurrences: list[SkillSpan] = Field(default_factory=list)
