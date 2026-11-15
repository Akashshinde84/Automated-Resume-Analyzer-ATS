import json
from io import BytesIO
from zipfile import ZipFile

from docx import Document
import pytest

from app.services.parser import ResumeParseError, ResumeParser, normalize_text, segment_sections


def save(tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_docx_extraction_order_unicode_sections(tmp_path, docx_bytes):
    result = ResumeParser().parsefile(save(tmp_path, "resume.DOCX", docx_bytes))
    assert "José 李明 — नमस्ते" in result["text"]
    assert "Université de Montréal" in result["sections"]["education"]
    assert result["sections"]["skills"] == "Python, SQL"
    assert "- Built APIs\n- Led a team" in result["sections"]["experience"]
    assert result["text"].index("Resume platform") < result["text"].index("Certifications")
    assert set(result["sections"]) == {"contact", "summary", "skills", "education", "experience", "projects", "certifications"}
    assert result["metadata"]["file_type"] == "docx"
    assert result["metadata"]["page_count"] is None
    json.dumps(result, ensure_ascii=False)


def test_pdf_extraction(tmp_path, make_pdf):
    content = make_pdf(["Jane Doe", "Summary", "Backend engineer", "Technical Skills", "Python", "Work History", "Built services"])
    result = ResumeParser().parsefile(save(tmp_path, "resume.pdf", content))
    assert result["sections"]["summary"] == "Backend engineer"
    assert result["sections"]["skills"] == "Python"
    assert result["sections"]["experience"] == "Built services"
    assert result["metadata"]["page_count"] == 1
    assert result["metadata"]["size_bytes"] == len(content)
    assert "\n" in result["text"]
    json.dumps(result)


def test_normalization_preserves_scripts_and_boundaries():
    text = "Jose\u0301\u00a0 李明\tनमस्ते\r\n\r\n\r\n• Python\u0000\fRésumé\u2028علي"
    assert normalize_text(text) == "José 李明 नमस्ते\n\n- Python\n\nRésumé\nعلي"


@pytest.mark.parametrize("heading, key", [("Work History", "experience"), ("Professional Experience", "experience"), ("Technical Skills", "skills"), ("Academic Background", "education")])
def test_heading_aliases_and_repetition(heading, key):
    sections, _ = segment_sections(f"{heading.upper()}:\nFirst\n{heading}\nSecond")
    assert sections[key] == "First\nSecond"


def test_heading_matching_does_not_consume_prose():
    sections, _ = segment_sections("Summary\nExperience building APIs\nSkills: Python")
    assert sections["summary"] == "Experience building APIs"
    assert sections["skills"] == "Python"


@pytest.mark.parametrize("name, content, code", [
    ("resume.txt", b"hello", "unsupported_type"),
    ("resume.pdf", b"", "empty_file"),
    ("resume.docx", b"", "empty_file"),
    ("resume.pdf", b"not pdf", "invalid_signature"),
    ("resume.docx", b"not docx", "invalid_signature"),
    ("resume.pdf", b"%PDF-1.7\nbroken", "corrupt_file"),
    ("resume.docx", b"PK\x03\x04broken", "corrupt_file"),
])
def test_invalid_documents(tmp_path, name, content, code):
    with pytest.raises(ResumeParseError) as caught:
        ResumeParser().parsefile(save(tmp_path, name, content))
    assert caught.value.code == code


def test_encrypted_pdf(tmp_path, make_pdf):
    with pytest.raises(ResumeParseError, match="Encrypted") as caught:
        ResumeParser().parsefile(save(tmp_path, "private.pdf", make_pdf(["Secret"], encrypted=True)))
    assert caught.value.code == "encrypted_pdf"


@pytest.mark.parametrize("image", [False, True])
def test_blank_and_image_only_pdf(tmp_path, make_pdf, image):
    result = ResumeParser().parsefile(save(tmp_path, "scan.pdf", make_pdf(image=image)))
    assert result["text"] == ""
    assert result["sections"] == {}
    assert any("No extractable text" in warning for warning in result["warnings"])
    assert result["metadata"]["image_only_pages"] == ([1] if image else [])


def test_empty_docx(tmp_path):
    stream = BytesIO()
    Document().save(stream)
    result = ResumeParser().parsefile(save(tmp_path, "empty.docx", stream.getvalue()))
    assert result["text"] == ""
    assert any("No extractable text" in warning for warning in result["warnings"])


def test_arbitrary_zip_is_not_docx(tmp_path):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("hello.txt", "hello")
    with pytest.raises(ResumeParseError) as caught:
        ResumeParser().parsefile(save(tmp_path, "fake.docx", stream.getvalue()))
    assert caught.value.code == "invalid_docx"


def test_docx_expansion_limit(tmp_path, docx_bytes):
    with pytest.raises(ResumeParseError) as caught:
        ResumeParser(max_docx_uncompressed_bytes=100).parsefile(save(tmp_path, "big.docx", docx_bytes))
    assert caught.value.code == "docx_expansion_limit"


def test_file_limit(tmp_path, make_pdf):
    with pytest.raises(ResumeParseError) as caught:
        ResumeParser(max_size_bytes=10).parsefile(save(tmp_path, "big.pdf", make_pdf(["Hello"])))
    assert caught.value.status_code == 413


def test_missing_file(tmp_path):
    with pytest.raises(ResumeParseError) as caught:
        ResumeParser().parsefile(tmp_path / "missing.pdf")
    assert caught.value.code == "unreadable_file"


def test_pdf_non_ascii_text(tmp_path, make_pdf):
    result = ResumeParser().parsefile(save(tmp_path, "unicode.pdf", make_pdf(["José", "Summary", "Résumé engineer"])))
    assert "José" in result["text"]
    assert "Résumé engineer" in result["sections"]["summary"]


def test_mixed_pdf_preserves_text_and_warns_for_image_page(tmp_path):
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from PIL import Image

    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(50, 750, "Skills: Python")
    pdf.showPage()
    pdf.drawImage(ImageReader(Image.new("RGB", (20, 20), "white")), 50, 500)
    pdf.showPage()
    pdf.save()
    result = ResumeParser().parsefile(save(tmp_path, "mixed.pdf", stream.getvalue()))
    assert result["sections"]["skills"] == "Python"
    assert result["metadata"]["page_count"] == 2
    assert result["metadata"]["image_only_pages"] == [2]
    assert any("Image-only" in warning for warning in result["warnings"])

    with pytest.raises(ResumeParseError) as caught:
        ResumeParser(max_pdf_pages=1).parsefile(tmp_path / "mixed.pdf")
    assert caught.value.code == "page_limit"


def test_corrupt_docx_xml(tmp_path):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<broken")
        archive.writestr("word/document.xml", "<broken")
        archive.writestr("_rels/.rels", "<broken")
    with pytest.raises(ResumeParseError) as caught:
        ResumeParser().parsefile(save(tmp_path, "corrupt.docx", stream.getvalue()))
    assert caught.value.code == "corrupt_file"


def test_pdf_cannot_be_disguised_as_docx(tmp_path, make_pdf):
    with pytest.raises(ResumeParseError) as caught:
        ResumeParser().parsefile(save(tmp_path, "fake.docx", make_pdf(["Hello"])))
    assert caught.value.code == "invalid_signature"
