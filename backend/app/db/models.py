"""Relational ownership/retention with JSON documents; no raw upload storage."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_owner_created", "owner_id", "created_at"), Index("ix_analyses_expires_at", "expires_at"))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_type: Mapped[str] = mapped_column(String(8), nullable=False)


class StructuredResume(Base):
    __tablename__ = "structured_resumes"
    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), primary_key=True)
    parsed: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    extraction: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class MatchResult(Base):
    __tablename__ = "match_results"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    analysis_id: Mapped[UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    job_description_id: Mapped[UUID] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
