"""Re-run the fixed synthetic gold without overwriting the historical baseline."""
import json
from pathlib import Path

from evaluate_nlp import evaluate, percent


def main():
    result = evaluate()
    result["limitations"] = [value for value in result["limitations"] if not value.startswith("Section accuracy")]
    result["limitations"] += [
        "Section presence uses the current heading vocabulary; boundary offsets are not measured.",
        "This corpus is reused diagnostic data, not held-out validation. The original private resume is unavailable.",
    ]
    root = Path(__file__).resolve().parents[2] / "docs/evaluation"
    (root / "extraction_revision_results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Extraction revision: measured synthetic diagnostics", "", "20 fictional profiles (10 PDF, 10 DOCX), unchanged gold labels.",
             "This is a reused diagnostic corpus, not representative or independently adjudicated validation.", "",
             "| Measure | Precision | Recall | F1 | TP / FP / FN |", "| --- | ---: | ---: | ---: | --- |"]
    for name, count in [("Canonical skills", result["skills_micro"]), ("Raw pretrained PERSON/ORG", result["entities_micro"]), *result["fields"].items()]:
        lines.append(f"| {name} | {percent(count['precision'])} | {percent(count['recall'])} | {percent(count['f1'])} | {count['tp']} / {count['fp']} / {count['fn']} |")
    section = result["section_presence"]
    lines += ["", f"Section presence: {section['correct_decisions']}/{section['decisions']}; exact section sets: {section['exact_documents']}/{section['documents']}.",
              "Presence denominators differ from the old seven-section baseline because activities/other boundaries are now recognized.",
              "", "Fields compare normalized value sets; they do not establish correct record-to-record association.",
              "New hyperlink/wrapped-record/layout cases are covered separately by test_layout_extraction.py; the original corpus does not label these new fields.",
              "The high precision of several fields reflects a small, easy set with few populated examples, not a general accuracy guarantee.",
              "Raw NER remains weak and has not improved: 22.00% F1 versus the historical 22.92%; text reading-order changes alter its context.",
              "No custom model was trained. Full per-case errors, model metadata and dataset SHA-256 are in the companion JSON.",
              "", "Reproduce: `backend/.venv/Scripts/python.exe backend/scripts/evaluate_extraction_revision.py`.", ""]
    (root / "extraction_revision_results.md").write_text("\n".join(lines), encoding="utf-8")
    print("Evaluated 20 synthetic profiles; separate revision metrics and per-case errors written.")
    return 0 if all(row["model"]["status"] == "available" for row in result["results"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
