"""Public typed analysis/history and integrated matching contracts."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.candidate import ExtractionResult
from app.schemas.matching import MatchingResponse, MatchingWeights, ParsedResumeInput
from app.schemas.skills import DetectedSkill


class FileMetadata(BaseModel):
    filename: str
    file_type: Literal["pdf", "docx"]
    size_bytes: int = Field(ge=0)
    characters: int = Field(ge=0)
    page_count: int | None = None
    image_only_pages: list[int] | None = None


class ParsedResumeData(BaseModel):
    text: str = Field(max_length=100_000)
    sections: dict[str, str]
    warnings: list[str]
    metadata: FileMetadata
    skills: list[DetectedSkill]
    skill_ontology_version: str


class AnalysisResponse(BaseModel):
    id: UUID | None = None
    stored: bool = False
    created_at: datetime
    expires_at: datetime | None = None
    parsed: ParsedResumeData
    extraction: ExtractionResult
    report_token: str | None = Field(default=None, max_length=1024)


class StoredMatch(BaseModel):
    id: UUID
    created_at: datetime
    job_description: str
    result: MatchingResponse


class AnalysisDetail(AnalysisResponse):
    matches: list[StoredMatch] = Field(default_factory=list)
    match_count: int = 0
    matches_limit: int = 20
    matches_offset: int = 0


class AnalysisSummary(BaseModel):
    id: UUID
    created_at: datetime
    expires_at: datetime
    file_type: Literal["pdf", "docx"]


class AnalysisPage(BaseModel):
    items: list[AnalysisSummary]
    total: int
    limit: int
    offset: int


class JobMatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_id: UUID | None = None
    resume: ParsedResumeInput | None = None
    job_description: str = Field(min_length=1, max_length=50_000)
    weights: MatchingWeights | None = None
    store: bool = False

    @field_validator("job_description")
    @classmethod
    def nonblank_job(cls, value):
        if not value.strip():
            raise ValueError("Job description must not be blank.")
        return value

    @model_validator(mode="after")
    def one_resume_source(self):
        if (self.analysis_id is None) == (self.resume is None):
            raise ValueError("Provide exactly one of analysis_id or resume.")
        if self.store and self.analysis_id is None:
            raise ValueError("Saving a match requires an existing stored analysis_id.")
        return self


class JobMatchResponse(BaseModel):
    id: UUID | None = None
    analysis_id: UUID | None = None
    stored: bool = False
    result: MatchingResponse
    report_token: str | None = Field(default=None, max_length=1024)
