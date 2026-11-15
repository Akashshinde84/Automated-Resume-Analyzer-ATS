from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
import phonenumbers


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Schema):
    field: str
    method: Literal["regex", "heuristic", "pretrained_ner", "phone_library"]
    rule: str
    source_text: str
    # Rule strength, not a calibrated model probability. NER scores are unavailable.
    confidence: Literal["low", "medium", "high"] | None = None


class NamedEntity(Schema):
    text: str
    label: Literal["PERSON", "ORG"]
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    confidence: float | None = None


class PhoneNumber(Schema):
    raw: str
    e164: str | None = None
    extension: str | None = None
    region: str | None = None
    status: Literal["valid", "ambiguous", "invalid"]


class Record(Schema):
    raw_text: str
    provenance: list[Evidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Education(Record):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class WorkExperience(Record):
    company: str | None = None
    job_title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class Project(Record):
    name: str | None = None
    description: str | None = None
    urls: list[str] = Field(default_factory=list)


class Certification(Record):
    name: str | None = None
    issuer: str | None = None
    date: str | None = None
    credential_id: str | None = None


class Candidate(Schema):
    name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[PhoneNumber] = Field(default_factory=list)
    linkedin_urls: list[str] = Field(default_factory=list)
    github_urls: list[str] = Field(default_factory=list)
    portfolio_urls: list[str] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    provenance: list[Evidence] = Field(default_factory=list)


class NLPMetadata(Schema):
    model: str
    model_version: str | None = None
    status: Literal["available", "unavailable"]
    custom_trained: Literal[False] = False
    language: str | None = None


class ExtractionResult(Schema):
    candidate: Candidate
    entities: list[NamedEntity] = Field(default_factory=list)
    nlp: NLPMetadata
    warnings: list[str] = Field(default_factory=list)


class ExtractionRequest(Schema):
    text: str = Field(max_length=100_000)
    phone_region: str | None = None

    @field_validator("phone_region")
    @classmethod
    def valid_region(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.upper()
            if value not in phonenumbers.SUPPORTED_REGIONS:
                raise ValueError("Use a supported two-letter phone region or null.")
        return value
