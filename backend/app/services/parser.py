"""Bounded PDF/DOCX text extraction and deterministic section segmentation."""
from pathlib import Path
import re
import unicodedata
from zipfile import BadZipFile, ZipFile

from app.services.sections import ALIASES, HEADINGS, heading_section
from app.services.skills import get_skill_extractor

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTImage, LTTextContainer
from pdfminer.pdfdocument import PDFDocument, PDFEncryptionError, PDFPasswordIncorrect
from pdfminer.pdfparser import PDFParser


class ResumeParseError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def normalize_text(text: str) -> str:
    # NFC preserves script distinctions; never ASCII-encode or strip combining marks.
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n")
    text = text.replace("\u2028", "\n").replace("\u2029", "\n\n")
    text = text.replace("\u00ad", "").replace("\ufeff", "")
    text = "".join(c for c in text if unicodedata.category(c) != "Cc" or c in "\n\t")
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[^\S\n]+", " ", line).strip()
        line = re.sub(r"^[•●▪◦‣⁃○■]\s*", "- ", line)
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def segment_sections(text: str) -> tuple[dict[str, str], list[str]]:
    buckets: dict[str, list[str]] = {}
    current = None
    preamble = []
    for line in text.splitlines():
        heading, separator, inline = line.partition(":")
        section = heading_section(line)
        if section:
            current = section
            buckets.setdefault(current, [])
            if separator and inline.strip():
                buckets[current].append(inline.strip())
        elif current:
            buckets[current].append(line)
        else:
            preamble.append(line)
    warnings = []
    if "\n".join(preamble).strip():
        # Keep introductory candidate text without claiming it is verified contact data.
        buckets["contact"] = preamble + [""] + buckets.get("contact", [])
        warnings.append("Text before the first recognized heading is grouped under contact; this is a heuristic.")
    return {key: "\n".join(value).strip() for key, value in buckets.items()}, warnings


def _has_image(item) -> bool:
    if isinstance(item, LTImage):
        return True
    return any(_has_image(child) for child in item) if hasattr(item, "__iter__") else False


def _blocks(container):
    for block in container.iter_inner_content():
        if isinstance(block, Paragraph):
            yield block.text
        elif isinstance(block, Table):
            for row in block.rows:
                seen = set()
                for cell in row.cells:
                    # Merged cells can occur more than once in a row.
                    if cell._tc not in seen:
                        seen.add(cell._tc)
                        yield "\n".join(_blocks(cell))


class ResumeParser:
    def __init__(self, max_size_bytes: int = 10 * 1024 * 1024,
                 max_docx_uncompressed_bytes: int = 50 * 1024 * 1024,
                 max_pdf_pages: int = 200):
        self.max_size_bytes = max_size_bytes
        self.max_docx_uncompressed_bytes = max_docx_uncompressed_bytes
        self.max_pdf_pages = max_pdf_pages

    def parsefile(self, filepath: str | Path) -> dict:
        path = Path(filepath)
        suffix = path.suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            raise ResumeParseError("unsupported_type", "Only PDF and DOCX files are supported.", 415)
        try:
            size = path.stat().st_size
            if size == 0:
                raise ResumeParseError("empty_file", "The uploaded file is empty.")
            if size > self.max_size_bytes:
                raise ResumeParseError("file_too_large", "The file exceeds the configured upload limit.", 413)
            with path.open("rb") as source:
                signature = source.read(8)
            expected = b"%PDF-" if suffix == ".pdf" else b"PK\x03\x04"
            if not signature.startswith(expected):
                raise ResumeParseError("invalid_signature", "File content does not match its extension.", 415)
            if suffix == ".pdf":
                raw, warnings, details = self._pdf(path)
            else:
                raw, warnings, details = self._docx(path)
        except ResumeParseError:
            raise
        except OSError as exc:
            raise ResumeParseError("unreadable_file", "The file could not be read.") from exc
        except Exception as exc:
            # Parser libraries raise many format-specific exceptions; never expose internals or paths.
            raise ResumeParseError("corrupt_file", "The document is corrupted or cannot be parsed.") from exc
        text = normalize_text(raw)
        sections, section_warnings = segment_sections(text)
        if not text:
            warnings.append("No extractable text was found. OCR is not implemented; no text has been inferred.")
        skill_extractor = get_skill_extractor()
        skills = skill_extractor.extract(text)
        return {
            "text": text,
            "skills": [skill.model_dump(mode="json") for skill in skills],
            "skill_ontology_version": skill_extractor.ontology.version,
            "sections": sections,
            "warnings": warnings + section_warnings,
            "metadata": {"filename": path.name, "file_type": suffix[1:], "size_bytes": size,
                         "characters": len(text), **details},
        }

    def _pdf(self, path: Path):
        try:
            with path.open("rb") as source:
                document = PDFDocument(PDFParser(source))
                if document.encryption:
                    raise ResumeParseError("encrypted_pdf", "Encrypted PDFs are not supported. Upload an unencrypted copy.")
            pages = []
            image_only = []
            no_text = []
            for number, page in enumerate(extract_pages(str(path)), start=1):
                if number > self.max_pdf_pages:
                    raise ResumeParseError("page_limit", "The PDF exceeds the configured page limit.", 413)
                content = "\n".join(item.get_text() for item in page if isinstance(item, LTTextContainer))
                pages.append(content)
                if not normalize_text(content):
                    no_text.append(number)
                    if _has_image(page):
                        image_only.append(number)
        except (PDFPasswordIncorrect, PDFEncryptionError) as exc:
            raise ResumeParseError("encrypted_pdf", "Encrypted PDFs are not supported. Upload an unencrypted copy.") from exc
        warnings = []
        if image_only:
            warnings.append(f"Image-only pages detected: {image_only}. They may be scanned; OCR is required to read them.")
        other_blank = sorted(set(no_text) - set(image_only))
        if other_blank:
            warnings.append(f"Pages without extractable text: {other_blank}. They may be blank or contain outlined text.")
        return "\n\n".join(pages), warnings, {"page_count": len(pages), "image_only_pages": image_only}

    def _docx(self, path: Path):
        with ZipFile(path) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if not {"[Content_Types].xml", "word/document.xml", "_rels/.rels"} <= names:
                raise ResumeParseError("invalid_docx", "The ZIP archive is not a valid DOCX document.", 415)
            if len(entries) > 2000 or sum(entry.file_size for entry in entries) > self.max_docx_uncompressed_bytes:
                raise ResumeParseError("docx_expansion_limit", "The DOCX archive exceeds the safe expansion limit.", 413)
            if any(entry.flag_bits & 1 for entry in entries):
                raise ResumeParseError("encrypted_docx", "Encrypted DOCX archives are not supported.")
            if archive.testzip() is not None:
                raise BadZipFile("Invalid ZIP checksum")
        document = Document(str(path))
        parts = []
        seen = set()
        for section in document.sections:
            for header in (section.header, section.first_page_header, section.even_page_header):
                if header.part not in seen:
                    seen.add(header.part)
                    parts.extend(_blocks(header))
        parts.extend(_blocks(document))
        for section in document.sections:
            for footer in (section.footer, section.first_page_footer, section.even_page_footer):
                if footer.part not in seen:
                    seen.add(footer.part)
                    parts.extend(_blocks(footer))
        return "\n".join(parts), ["DOCX text boxes, drawings, and tracked revisions may not be extracted; page count is unavailable."], {"page_count": None}
