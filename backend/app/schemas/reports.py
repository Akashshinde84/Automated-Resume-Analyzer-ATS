"""Report sources are either owned records or verifiable API snapshots."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.analysis import AnalysisResponse, JobMatchResponse
from app.schemas.matching import MatchingResponse


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["json", "pdf"]
    analysis_id: UUID | None = None
    snapshot: AnalysisResponse | None = None
    match_id: UUID | None = None
    match: JobMatchResponse | None = None
    job_description: str | None = Field(default=None, min_length=1, max_length=50_000)

    @model_validator(mode="after")
    def valid_sources(self):
        if (self.analysis_id is None) == (self.snapshot is None):
            raise ValueError("Provide exactly one analysis_id or signed snapshot.")
        if self.snapshot and (self.snapshot.id or self.snapshot.stored):
            raise ValueError("Saved analyses must be retrieved by analysis_id.")
        if self.match_id and (not self.analysis_id or self.match or self.job_description is not None):
            raise ValueError("Saved matches require analysis_id and cannot be combined with another match source.")
        if (self.match is None) != (self.job_description is None):
            raise ValueError("A signed match and its original job_description must be supplied together.")
        if self.match and (self.match.id or self.match.stored):
            raise ValueError("Saved matches must be retrieved by match_id.")
        return self


class ReportMatch(BaseModel):
    id: UUID | None = None
    job_description: str
    result: MatchingResponse


class AnalysisReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    analysis: AnalysisResponse
    match: ReportMatch | None = None
    privacy_notice: str = "Contains personal information. Keep this download private. Deleting server records does not delete downloaded copies."
    limitations: list[str] = Field(default_factory=lambda: [
        "Extraction uses regex, heuristics and pretrained NER; missing fields are not inferred.",
        "Recognized skills indicate mentions, not verified proficiency. OCR is not enabled.",
        "Compatibility is a project-defined estimate, not an ATS score, hiring probability or hiring decision.",
        "Text similarity is lexical TF-IDF cosine similarity, not semantic embeddings.",
    ])
