"""Typed matching contract; parser metadata and client skill claims are not scored."""
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.skills import SkillCategory


class ParsedResumeInput(BaseModel):
    # Accept complete Phase 4 parser responses, but trust/re-extract only their text.
    model_config = ConfigDict(extra="ignore")
    text: str = Field(max_length=100_000)


class MatchingWeights(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: float = Field(default=0.7, ge=0, le=1, allow_inf_nan=False)
    text: float = Field(default=0.3, ge=0, le=1, allow_inf_nan=False)
    required_importance: float = Field(default=2.0, gt=0, le=100, allow_inf_nan=False)
    preferred_importance: float = Field(default=1.0, gt=0, le=100, allow_inf_nan=False)
    unspecified_importance: float = Field(default=1.0, gt=0, le=100, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_total(self):
        if not math.isclose(self.skills + self.text, 1.0, abs_tol=1e-9):
            raise ValueError("Skill and text weights must sum to 1.")
        return self


class MatchingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resume: ParsedResumeInput
    job_description: str = Field(max_length=50_000)
    weights: MatchingWeights | None = None


class Evidence(BaseModel):
    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    section: str
    context: str | None = Field(default=None, max_length=400)


class JobSkill(BaseModel):
    name: str
    category: SkillCategory
    importance: Literal["required", "preferred", "unspecified"]
    job_evidence: list[Evidence] = Field(default_factory=list)


class SkillComparison(JobSkill):
    matched: bool
    resume_evidence: list[Evidence] = Field(default_factory=list)


class FeatureContribution(BaseModel):
    feature: str
    kind: Literal["skill", "task"]
    cosine_contribution: float = Field(ge=0, le=1)


class Suggestion(BaseModel):
    code: Literal["surface_existing_evidence", "review_requirement_gap", "review_preferred_gap"]
    skill: str
    message: str
    resume_evidence: list[Evidence] = Field(default_factory=list)


class MatchingScores(BaseModel):
    skill_overlap: float | None = Field(default=None, ge=0, le=100)
    text_similarity: float | None = Field(default=None, ge=0, le=100)
    overall: float | None = Field(default=None, ge=0, le=100)


class MatchingResponse(BaseModel):
    status: Literal["computed", "insufficient_input", "no_supported_job_skills"]
    scores: MatchingScores
    weights: MatchingWeights
    effective_weights: dict[str, float]
    formula: str
    score_meaning: str = "Project-defined compatibility estimate; not an ATS score, hiring probability, or hiring/rejection recommendation."
    ontology_version: str
    required_skills: list[JobSkill]
    preferred_skills: list[SkillComparison]
    unspecified_skills: list[SkillComparison]
    matched_skills: list[SkillComparison]
    missing_required_skills: list[JobSkill]
    suggestions: list[Suggestion]
    shared_text_features: list[FeatureContribution]
    warnings: list[str]
    method: str = "Pair-local binary TF-IDF and cosine over canonical skill and allowlisted task tokens; no embeddings or custom-trained predictor."
