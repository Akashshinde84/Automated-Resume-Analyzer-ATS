"""Additive document provenance, never a substitute for missing OCR text."""
from typing import Literal
from pydantic import BaseModel, Field


class DocumentLink(BaseModel):
    url: str = Field(max_length=2048)
    label: str = Field(default="", max_length=500)
    source: Literal["pdf_annotation", "docx_relationship"]
    page: int | None = None
    bbox: list[float] | None = None
    text_start: int | None = None
    block_index: int | None = None
    ambiguous: bool = False


class LayoutBlock(BaseModel):
    text: str
    page: int | None = None
    bbox: list[float] | None = None
    font_size: float | None = None
    bold: bool = False
