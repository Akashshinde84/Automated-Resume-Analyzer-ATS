"""Generate and evaluate a pre-labeled synthetic corpus. No training or tuning.

Distinct-value micro precision/recall/F1, section-presence accuracy, exact field
coverage and empty-field behavior are deliberately separate measures.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from docx import Document
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from app.services.extraction import InformationExtractor
from app.services.parser import ResumeParser
from app.services.sections import HEADINGS
from app.services.skills import get_skill_extractor

DATASET = ROOT / "docs/evaluation/resumes.json"
FIELDS = ("name", "emails", "phones", "institution", "degree", "field", "company", "job_title", "work_start", "work_end", "project", "certification")


def normalized(value):
    return " ".join(unicodedata.normalize("NFC", str(value)).casefold().split())


def values(items):
    return {normalized(item) for item in items if item is not None and str(item).strip()}


def metric(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def compare(expected, actual):
    return Counter(tp=len(expected & actual), fp=len(actual - expected), fn=len(expected - actual))


def generate(case, path):
    lines, layout = case["lines"], case["layout"]
    if case["format"] == "docx":
        document = Document()
        body = lines
        if layout == "header":
            document.sections[0].header.paragraphs[0].text = "\n".join(lines[:2])
            body = lines[2:]
        if layout == "table":
            table = document.add_table(rows=0, cols=2)
            for index in range(0, len(body), 2):
                cells = table.add_row().cells
                cells[0].text = body[index]
                cells[1].text = body[index + 1] if index + 1 < len(body) else ""
        else:
            for line in body:
                document.add_paragraph(line)
        document.save(path)
        return
    if "EvaluationVera" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("EvaluationVera", str(Path(reportlab.__file__).parent / "fonts/Vera.ttf")))
    pdf = canvas.Canvas(str(path), pagesize=(612, 792))
    pdf.setTitle("Synthetic evaluation resume " + case["id"])
    for index, line in enumerate(lines):
        if layout == "multipage" and index == 8:
            pdf.showPage()
        pdf.setFont("EvaluationVera", 9 if layout != "two_column" else 8)
        if layout == "two_column":
            split = len(lines) // 2
            column, row = (0, index) if index < split else (1, index - split)
            x, y = 35 + column * 285, 745 - row * 24
        else:
            row = index - 8 if layout == "multipage" and index >= 8 else index
            x, y = 40, 745 - row * 23
        pdf.drawString(x, y, line)
    pdf.save()


def candidate_fields(candidate):
    return {
        "name": [candidate.name] if candidate.name else [], "emails": candidate.emails,
        "phones": [phone.e164 for phone in candidate.phones if phone.e164],
        "institution": [e.institution for e in candidate.education],
        "degree": [e.degree for e in candidate.education], "field": [e.field for e in candidate.education],
        "company": [e.company for e in candidate.work_experience], "job_title": [e.job_title for e in candidate.work_experience],
        "work_start": [e.start_date for e in candidate.work_experience], "work_end": [e.end_date for e in candidate.work_experience],
        "project": [e.name for e in candidate.projects], "certification": [e.name for e in candidate.certifications],
    }


def evaluate():
    raw = DATASET.read_bytes()
    dataset = json.loads(raw)
    canonical = {skill.name for skill in get_skill_extractor().ontology.skills}
    cases = dataset["cases"]
    assert len(cases) == 20 and len({case["id"] for case in cases}) == 20
    for case in cases:
        assert set(case["gold"]["skills"]) <= canonical, (case["id"], set(case["gold"]["skills"]) - canonical)
    extractor = InformationExtractor()
    skill_counts, entity_counts = Counter(), Counter()
    entity_by_label = {label: Counter() for label in ("PERSON", "ORG")}
    field_counts = {field: Counter() for field in FIELDS}
    rows, sections_total, sections_correct, exact_sections = [], 0, 0, 0
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="nlp-evaluation-", dir=ROOT / ".tmp") as directory:
        for case in cases:
            path = Path(directory) / (case["id"] + "." + case["format"])
            generate(case, path)
            parsed = ResumeParser().parsefile(path)
            extracted = extractor.extract(parsed["text"])
            expected_skills, actual_skills = values(case["gold"]["skills"]), values(skill["name"] for skill in parsed["skills"])
            skill_counts.update(compare(expected_skills, actual_skills))
            gold_sections = set(case["gold"]["sections"])
            actual_sections = {key for key, value in parsed["sections"].items() if value.strip()}
            sections_correct += sum((section in gold_sections) == (section in actual_sections) for section in HEADINGS)
            sections_total += len(HEADINGS)
            exact_sections += gold_sections == actual_sections
            entity_errors = {}
            for label in entity_by_label:
                gold = values(case["gold"]["entities"][label])
                predicted = values(entity.text for entity in extracted.entities if entity.label == label)
                counts = compare(gold, predicted)
                entity_counts.update(counts); entity_by_label[label].update(counts)
                entity_errors[label] = {"missing": sorted(gold - predicted), "extra": sorted(predicted - gold)}
            actual_fields, field_errors = candidate_fields(extracted.candidate), {}
            for field in FIELDS:
                gold, actual = values(case["gold"]["fields"].get(field, [])), values(actual_fields[field])
                counts = field_counts[field]
                counts.update(compare(gold, actual))
                counts["cases"] += 1
                counts["exact_cases"] += gold == actual
                counts["populated_gold_cases"] += bool(gold)
                counts["successful_populated_cases"] += bool(gold) and gold == actual
                counts["empty_gold_cases"] += not gold
                counts["correct_empty_cases"] += not gold and not actual
                if gold != actual:
                    field_errors[field] = {"expected": sorted(gold), "actual": sorted(actual)}
            rows.append({"id": case["id"], "format": case["format"], "layout": case["layout"],
                         "characters": parsed["metadata"]["characters"], "model": extracted.nlp.model_dump(),
                         "skills": {"missing": sorted(expected_skills - actual_skills), "extra": sorted(actual_skills - expected_skills)},
                         "sections": {"missing": sorted(gold_sections - actual_sections), "extra": sorted(actual_sections - gold_sections)},
                         "entity_errors": entity_errors, "field_errors": field_errors})
    fields = {}
    for field, count in field_counts.items():
        fields[field] = {**dict(count), **metric(count["tp"], count["fp"], count["fn"]),
                         "exact_case_rate": count["exact_cases"] / count["cases"],
                         "populated_success_rate": count["successful_populated_cases"] / count["populated_gold_cases"] if count["populated_gold_cases"] else None}
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "dataset_sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(cases), "formats": dict(Counter(case["format"] for case in cases)),
            "skills_micro": metric(**skill_counts), "entities_micro": metric(**entity_counts),
            "entities_by_label": {label: metric(**count) for label, count in entity_by_label.items()},
            "section_presence": {"correct_decisions": sections_correct, "decisions": sections_total, "accuracy": sections_correct / sections_total,
                                 "exact_documents": exact_sections, "documents": len(cases), "exact_document_rate": exact_sections / len(cases)},
            "fields": fields, "results": rows,
            "limitations": ["Synthetic developer-authored diagnostic set; not independently human reviewed or representative.",
                            "No held-out real-world corpus, confidence intervals, hiring outcomes, fairness or calibration claim.",
                            "Entity scores compare unique exact normalized PERSON/ORG values per resume, not BIO spans.",
                            "Field sets measure value recovery, not alignment of multiple employment/education records.",
                            "Section accuracy measures seven binary presence decisions per document, not boundary offsets."]}


def percent(value):
    return "n/a" if value is None else f"{100 * value:.2f}%"


def main():
    report = evaluate()
    target = ROOT / "docs/evaluation"
    (target / "nlp_results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Synthetic NLP evaluation", "", f"{report['cases']} profiles: {report['formats']}. Dataset SHA-256: `{report['dataset_sha256']}`.",
             "", "| Measure | Precision | Recall | F1 | TP / FP / FN |", "| --- | ---: | ---: | ---: | --- |"]
    for label, scores in [("Skills", report["skills_micro"]), ("Pretrained NER", report["entities_micro"]), *report["entities_by_label"].items()]:
        lines.append(f"| {label} | {percent(scores['precision'])} | {percent(scores['recall'])} | {percent(scores['f1'])} | {scores['tp']} / {scores['fp']} / {scores['fn']} |")
    section = report["section_presence"]
    lines += ["", f"Section presence: {section['correct_decisions']}/{section['decisions']} = {percent(section['accuracy'])}. Exact section sets: {section['exact_documents']}/{section['documents']} = {percent(section['exact_document_rate'])}.",
              "", "| Field | Correct complete populated cases | Populated success | Exact cases including empty |", "| --- | --- | ---: | --- |"]
    for field, count in report["fields"].items():
        lines.append(f"| {field} | {count['successful_populated_cases']}/{count['populated_gold_cases']} | {percent(count['populated_success_rate'])} | {count['exact_cases']}/{count['cases']} |")
    lines += ["", "## Scope and limitations", "", *["- " + value for value in report["limitations"]],
              "", "Gold labels were authored before predictions. No human relevance adjudication or custom NER training occurred. Per-case errors and model availability are in nlp_results.json. Do not interpret high synthetic skill scores as real-world accuracy.",
              "", "Reproduce from repository root: `backend/.venv/Scripts/python.exe backend/scripts/evaluate_nlp.py`.", ""]
    (target / "nlp_results.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("cases", "skills_micro", "entities_micro", "section_presence")}, indent=2))
    # Model absence makes the NER evaluation invalid, rather than pretending it ran.
    return 0 if all(row["model"]["status"] == "available" for row in report["results"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
