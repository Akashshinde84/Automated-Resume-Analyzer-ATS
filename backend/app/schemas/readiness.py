"""Versioned, auditable document-quality estimate independent of any job."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReadinessWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact: int = Field(default=10, ge=0, le=100)
    structure: int = Field(default=20, ge=0, le=100)
    skills: int = Field(default=15, ge=0, le=100)
    descriptions: int = Field(default=20, ge=0, le=100)
    qualifications: int = Field(default=10, ge=0, le=100)
    readability: int = Field(default=15, ge=0, le=100)
    clarity: int = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def total(self):
        if sum(self.model_dump().values()) != 100:
            raise ValueError("Readiness category maximums must sum to 100.")
        return self


class ReadinessCheck(BaseModel):
    code: str
    label: str
    earned: float = Field(ge=0)
    maximum: float = Field(ge=0)
    reason: str
    evidence: list[str] = Field(default_factory=list)


class ReadinessCategory(BaseModel):
    key: str
    label: str
    score: float = Field(ge=0)
    maximum: int = Field(ge=0, le=100)
    checks: list[ReadinessCheck]


class Improvement(BaseModel):
    code: str
    priority: Literal["high", "medium", "low"]
    problem: str
    why: str
    section: str
    suggestion: str
    possible_points: float | None = Field(default=None, ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)


class ReadinessResult(BaseModel):
    version: Literal["1.0.0"] = "1.0.0"
    status: Literal["computed", "insufficient_text"]
    score: float | None = Field(default=None, ge=0, le=100)
    label: str = "Project-defined ATS readiness estimate; not an official employer ATS score or a hiring prediction."
    formula: str = "score = sum(category score); category score = category maximum * sum(base points earned) / sum(base points available). Each category is rounded to 2 decimals before summing."
    categories: list[ReadinessCategory]
    strengths: list[str]
    recommendations: list[Improvement]
    limitations: list[str]
