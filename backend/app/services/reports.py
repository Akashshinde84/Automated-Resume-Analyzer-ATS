"""ReportLab presentation from a single validated report; no disk staging or networking."""
from io import BytesIO
from pathlib import Path
from threading import Lock
from html import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

FONT_LOCK = Lock()
TEAL = colors.HexColor("#087f75")
INK = colors.HexColor("#1c3446")
MUTED = colors.HexColor("#5e7280")


def report_fonts():
    with FONT_LOCK:
        if "ResumeVera" not in pdfmetrics.getRegisteredFontNames():
            root = Path(reportlab.__file__).parent / "fonts"
            pdfmetrics.registerFont(TTFont("ResumeVera", str(root / "Vera.ttf")))
            pdfmetrics.registerFont(TTFont("ResumeVeraBold", str(root / "VeraBd.ttf")))
    regular = set(pdfmetrics.getFont("ResumeVera").face.charToGlyph)
    bold = set(pdfmetrics.getFont("ResumeVeraBold").face.charToGlyph)
    return regular & bold


def format_score(value):
    return "Not available" if value is None else f"{value:.1f} / 100"


class PDFReport:
    """Bounded presentation with explicit omissions; JSON retains the full source.

    ReportLab's bundled Vera fonts are embedded. Unsupported glyphs become visible
    Unicode codepoints rather than silent replacement boxes or discarded data.
    All untrusted values are XML-escaped; links/images/markup are never interpreted.
    """
    def __init__(self):
        self.glyphs = report_fonts()
        self.story = []
        self.remaining = 60_000
        self.omitted = False
        self.unsupported = False
        self.styles = {
            "title": ParagraphStyle("ReportTitle", fontName="ResumeVeraBold", fontSize=25, leading=32, textColor=INK, spaceAfter=12),
            "heading": ParagraphStyle("ReportHeading", fontName="ResumeVeraBold", fontSize=13, leading=19, textColor=TEAL, spaceBefore=20, spaceAfter=9, keepWithNext=True),
            "subheading": ParagraphStyle("ReportSubheading", fontName="ResumeVeraBold", fontSize=10, leading=15, textColor=INK, spaceBefore=10, spaceAfter=5, keepWithNext=True),
            "body": ParagraphStyle("ReportBody", fontName="ResumeVera", fontSize=9, leading=14, textColor=INK, alignment=TA_LEFT, spaceAfter=6, splitLongWords=True),
            "small": ParagraphStyle("ReportSmall", fontName="ResumeVera", fontSize=8, leading=12, textColor=MUTED, spaceAfter=6, splitLongWords=True),
        }

    def text(self, value):
        chars = []
        for char in str(value):
            if char in "\r\n\t":
                chars.append(" " if char == "\t" else char)
            elif char in "\u2010\u2011\u2012\u2013\u2014\u2212":
                chars.append("-")
            elif ord(char) in self.glyphs and char.isprintable():
                chars.append(char)
            else:
                self.unsupported = True
                chars.append(f"[U+{ord(char):04X}]")
        return escape("".join(chars), quote=False).replace("\n", "<br/>")

    def add(self, value, style="body", *, trusted=False):
        value = str(value)
        if not trusted:
            if self.remaining <= 0:
                self.omitted = True
                return
            if len(value) > self.remaining:
                value = value[:self.remaining] + " [Presentation limit reached; see JSON report.]"
                self.omitted = True
            self.remaining -= len(value)
        # Chunk long single paragraphs so a huge bullet/URL cannot create an
        # unsplittable flowable. All chunks still belong to the same source.
        for start in range(0, max(1, len(value)), 3000):
            self.story.append(Paragraph(self.text(value[start:start + 3000]), self.styles[style]))

    def heading(self, label):
        if self.remaining > 0:
            self.add(label, "heading", trusted=True)

    def evidence(self, items, label):
        for item in items:
            source = item.context or item.text
            self.add(f"{label} [{item.section}; characters {item.start}-{item.end}]: {source}", "small")

    def records(self, title, records, fields):
        self.heading(title)
        if not records:
            self.add("Not identified.", "small")
        for record in records:
            for field, label in fields:
                self.add(f"{label}: {getattr(record, field) or 'Not identified'}")
            if getattr(record, "description", None):
                self.add(record.description)
            if getattr(record, "urls", None):
                self.add("Links: " + "; ".join(record.urls))
            self.add("Source: " + record.raw_text, "small")
            for warning in record.warnings:
                self.add("Extraction note: " + warning, "small")
            self.story.append(Spacer(1, 5))

    def render(self, report):
        analysis, match = report.analysis, report.match
        candidate = analysis.extraction.candidate
        self.add("RESUME ATLAS / PRIVATE ANALYSIS", "small", trusted=True)
        self.add("Resume analysis report", "title", trusted=True)
        self.add(f"Generated {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')} | Report schema {report.schema_version}", "small")
        self.add(report.privacy_notice, "small")
        self.story.append(HRFlowable(width="100%", thickness=1.5, color=TEAL, spaceBefore=10, spaceAfter=14))
        self.add(candidate.name or "Name not identified", "subheading")
        self.add(f"Source file: {analysis.parsed.metadata.filename} | {analysis.parsed.metadata.file_type.upper()} | {analysis.parsed.metadata.characters} extracted characters", "small")
        self.add(f"Analysis ID: {analysis.id or 'Stateless - not saved'}", "small")
        if analysis.expires_at:
            self.add("Server record expires: " + analysis.expires_at.isoformat(), "small")

        if match:
            result = match.result
            self.heading("01 / Job compatibility")
            self.add("Overall estimate: " + format_score(result.scores.overall), "subheading")
            self.add(f"Skill coverage: {format_score(result.scores.skill_overlap)} | Text similarity: {format_score(result.scores.text_similarity)}")
            self.add(result.score_meaning, "small")
            self.add("Formula: " + result.formula)
            self.add("Effective weights: " + "; ".join(f"{key}: {value * 100:.1f}%" for key, value in result.effective_weights.items()), "small")
            self.add(f"Required/preferred/unspecified importance: {result.weights.required_importance:g} / {result.weights.preferred_importance:g} / {result.weights.unspecified_importance:g}", "small")
            self.add(result.method, "small")
        else:
            self.heading("01 / Job compatibility")
            self.add("No job comparison included. No score has been generated for this report.")

        self.heading("02 / Candidate details")
        self.add("Email: " + (", ".join(candidate.emails) or "Not identified"))
        self.add("Phone: " + ("; ".join((p.e164 or p.raw) + (f" ext. {p.extension}" if p.extension else "") + f" ({p.status})" for p in candidate.phones) or "Not identified"))
        for title, values in (("LinkedIn", candidate.linkedin_urls), ("GitHub", candidate.github_urls), ("Portfolio", candidate.portfolio_urls)):
            self.add(title + ": " + ("; ".join(values) or "Not identified"))
        if analysis.parsed.sections.get("summary"):
            self.add("Summary", "subheading")
            self.add(analysis.parsed.sections["summary"])

        self.heading("03 / Extracted skills and resume evidence")
        if not analysis.parsed.skills:
            self.add("No ontology skills identified.")
        for skill in analysis.parsed.skills:
            self.add(f"{skill.name} | {skill.category} | {'Explicitly listed' if skill.explicitly_listed else 'Mentioned in context'}", "subheading")
            for occurrence in skill.occurrences:
                self.add(f"{occurrence.section} / {occurrence.source_type} [{occurrence.start}-{occurrence.end}]: {occurrence.text}", "small")
        self.records("04 / Work experience", candidate.work_experience, [("company", "Company"), ("job_title", "Role"), ("start_date", "Start"), ("end_date", "End")])
        self.records("05 / Education", candidate.education, [("institution", "Institution"), ("degree", "Degree"), ("field", "Field"), ("start_date", "Start"), ("end_date", "End")])
        self.records("06 / Projects", candidate.projects, [("name", "Project")])
        self.records("07 / Certifications", candidate.certifications, [("name", "Certification"), ("issuer", "Issuer"), ("date", "Date"), ("credential_id", "Credential")])

        if match:
            result = match.result
            self.heading("08 / Job skill comparison")
            for label, skills in (("Matched skills", result.matched_skills), ("Missing required skills", result.missing_required_skills), ("Preferred skills", result.preferred_skills), ("Unspecified requirements", result.unspecified_skills)):
                self.add(label, "subheading")
                if not skills:
                    self.add("None identified in the supported ontology.", "small")
                for skill in skills:
                    status = " | Found" if getattr(skill, "matched", None) is True else " | Not found" if getattr(skill, "matched", None) is False else ""
                    self.add(f"{skill.name} ({skill.importance}){status}")
                    self.evidence(skill.job_evidence, "Job")
                    self.evidence(getattr(skill, "resume_evidence", []), "Resume")
            self.heading("09 / Evidence-based next steps")
            self.add("Add qualifications only when true and supported by your own experience.", "small")
            if not result.suggestions:
                self.add("No evidence-based suggestions available.")
            for suggestion in result.suggestions:
                self.add(suggestion.skill, "subheading")
                self.add(suggestion.message)
                self.evidence(suggestion.resume_evidence, "Resume")
            self.heading("10 / Job description used")
            self.add(match.job_description)

        # These notices bypass the presentation budget so limits are never hidden.
        self.remaining = max(self.remaining, 4000)
        self.heading("Notes and limitations")
        warnings = [*analysis.parsed.warnings, *analysis.extraction.warnings]
        if match:
            warnings += match.result.warnings
        for note in dict.fromkeys([*warnings, *report.limitations]):
            self.add(note, "small")
        self.add(f"NER model: {analysis.extraction.nlp.model} ({analysis.extraction.nlp.status}); custom trained: no. Skill ontology: {analysis.parsed.skill_ontology_version}.", "small")
        if self.omitted:
            self.add("This PDF reached its 60,000-character presentation budget. Some content is omitted. The JSON report retains the complete structured data and evidence.", "small", trusted=True)
        if self.unsupported:
            self.add("Font coverage note: unsupported characters are displayed as [U+XXXX] Unicode codepoints. Download JSON for original Unicode text; no candidate information is inferred.", "small", trusted=True)

        output = BytesIO()
        document = SimpleDocTemplate(output, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=54, bottomMargin=50,
                                     title="Private resume analysis", author="Resume Atlas", subject="Authorized resume analysis and optional job comparison")

        def decorate(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor("#dfe8e5"))
            canvas.line(48, 39, A4[0] - 48, 39)
            canvas.setFont("ResumeVera", 7)
            canvas.setFillColor(MUTED)
            canvas.drawString(48, 25, "RESUME ATLAS | PRIVATE | Compatibility estimate - human review required")
            canvas.drawRightString(A4[0] - 48, 25, f"Page {doc.page}")
            canvas.restoreState()

        document.build(self.story, onFirstPage=decorate, onLaterPages=decorate)
        return output.getvalue()
