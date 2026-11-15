"""Generate synthetic documents at test time; no candidate files in Git."""
from io import BytesIO

from docx import Document
import pytest
from reportlab.pdfgen import canvas
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.lib.utils import ImageReader
from PIL import Image


@pytest.fixture
def docx_bytes():
    document = Document()
    document.sections[0].header.paragraphs[0].text = "José 李明 — नमस्ते"
    document.add_paragraph("Contact")
    document.add_paragraph("jose@example.test")
    document.add_paragraph("Professional Summary")
    document.add_paragraph("Builds reliable software.")
    document.add_paragraph("Technical Skills: Python, SQL")
    document.add_paragraph("Academic Background")
    document.add_paragraph("Université de Montréal")
    document.add_paragraph("Professional Experience")
    document.add_paragraph("• Built APIs\n• Led a team")
    document.add_paragraph("Projects")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Resume platform"
    table.cell(0, 1).text = "React"
    document.add_paragraph("Certifications")
    document.add_paragraph("Cloud certificate")
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


@pytest.fixture
def make_pdf():
    def create(lines=(), *, image=False, encrypted=False):
        stream = BytesIO()
        encryption = StandardEncryption("secret", ownerPassword="owner") if encrypted else None
        pdf = canvas.Canvas(stream, encrypt=encryption)
        y = 780
        for line in lines:
            pdf.drawString(50, y, line)
            y -= 20
        if image:
            picture = Image.new("RGB", (20, 20), "white")
            pdf.drawImage(ImageReader(picture), 50, 500, width=100, height=100)
        pdf.showPage()
        pdf.save()
        return stream.getvalue()
    return create


@pytest.fixture(autouse=True)
def explicit_local_mode_for_legacy_tests(monkeypatch):
    """Earlier unauthenticated processing tests run in explicitly local mode.

    Phase 6 security tests pass app_mode='single_user' explicitly. New history and
    integrated endpoints always require a token, including in local mode.
    """
    monkeypatch.setenv("APP_MODE", "local")
