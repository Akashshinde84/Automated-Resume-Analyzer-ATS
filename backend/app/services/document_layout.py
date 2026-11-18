"""Bounded layout and hyperlink capture using the existing pdfminer/docx stack."""
from pdfminer.layout import LTChar, LTTextLine
from pdfminer.pdftypes import resolve1
from pdfminer.psparser import literal_name
from docx.text.paragraph import Paragraph
import math

from app.services.document_links import normalize_document_target


def pdf_lines(page, number):
    result = []
    def visit(item):
        if isinstance(item, LTTextLine):
            text = item.get_text().strip()
            if text:
                chars = [c for c in item if isinstance(c, LTChar)]
                result.append(dict(text=text, page=number, bbox=list(item.bbox),
                                   font_size=round(max((c.size for c in chars), default=0), 2),
                                   bold=bool(chars) and sum("bold" in c.fontname.lower() for c in chars) > len(chars) / 2))
        elif hasattr(item, "__iter__"):
            for child in item:
                visit(child)
    visit(page)
    return result


def reading_order(lines, width):
    """Gutter heuristic with full-width separators; date sidebars remain row-local."""
    split = width / 2
    left = [b for b in lines if b["bbox"][2] < split - 8]
    right = [b for b in lines if b["bbox"][0] > split + 8]
    from app.services.dates import DATE
    date_sidebar = right and sum(bool(DATE.search(b["text"])) for b in right) > len(right) / 2
    if len(left) < 3 or len(right) < 3 or date_sidebar:
        ordered = sorted(lines, key=lambda b: (-round(b["bbox"][3] / 3), b["bbox"][0]))
        # Same-baseline fragments (e.g. qualification and right-aligned dates).
        merged = []
        for b in ordered:
            if merged and abs(merged[-1]["bbox"][3] - b["bbox"][3]) < 3 and b["bbox"][0] >= merged[-1]["bbox"][2]:
                previous = merged[-1]
                previous = {**previous, "text": previous["text"] + " | " + b["text"],
                            "bbox": [previous["bbox"][0], min(previous["bbox"][1], b["bbox"][1]), b["bbox"][2], max(previous["bbox"][3], b["bbox"][3])]}
                merged[-1] = previous
            else:
                merged.append(b)
        return merged, False
    spanning = sorted([b for b in lines if b not in left and b not in right], key=lambda b: -b["bbox"][3])
    result, remaining = [], list(lines)
    for separator in spanning:
        above = [b for b in remaining if b["bbox"][3] > separator["bbox"][3] + 2]
        result.extend(sorted(above, key=lambda b: (b["bbox"][0] >= split, -b["bbox"][3], b["bbox"][0])))
        result.append(separator)
        remaining = [b for b in remaining if b not in above and b is not separator]
    result.extend(sorted(remaining, key=lambda b: (b["bbox"][0] >= split, -b["bbox"][3], b["bbox"][0])))
    return result, True


def pdf_annotations(page, number):
    links = []
    for ref in (resolve1(page.annots) or [])[:1000]:
        annotation = resolve1(ref)
        if not isinstance(annotation, dict):
            continue
        action = resolve1(annotation.get("A"))
        if not isinstance(action, dict) or not action.get("S") or literal_name(action["S"]) != "URI":
            continue
        uri = resolve1(action.get("URI"))
        if isinstance(uri, bytes):
            uri = uri.decode("utf-8", errors="replace")
        url = normalize_document_target(uri) if isinstance(uri, str) else None
        rect = resolve1(annotation.get("Rect"))
        if url and isinstance(rect, (list, tuple)) and len(rect) == 4:
            try:
                coordinates = [float(x) for x in rect]
                if all(math.isfinite(x) for x in coordinates):
                    links.append(dict(url=url, label="", source="pdf_annotation", page=number, bbox=coordinates))
            except (TypeError, ValueError):
                continue
    return links


def associate_links(links, lines):
    for link in links:
        x0, y0, x1, y1 = link["bbox"]
        matches = [b for b in lines if b["bbox"][0] < x1 and b["bbox"][2] > x0 and b["bbox"][1] < y1 and b["bbox"][3] > y0]
        link["label"] = " ".join(b["text"] for b in matches)[:500]


def docx_blocks(container, links, blocks):
    from docx.table import Table
    for block in container.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text
            if block.style and block.style.name.startswith("List") and text and not text.startswith(("-", "•")):
                text = "- " + text
            blocks.append(dict(text=text, page=None, bbox=None, font_size=None,
                               bold=any(run.bold for run in block.runs) or bool(block.style and block.style.name.startswith("Heading"))))
            for item in block.iter_inner_content():
                if hasattr(item, "url"):
                    url = normalize_document_target(item.url)
                    if url and len(links) < 500:
                        links.append(dict(url=url, label=item.text[:500], source="docx_relationship", page=None, bbox=None, block_index=len(blocks) - 1))
            yield text
        elif isinstance(block, Table):
            seen = set()
            for row in block.rows:
                for cell in row.cells:
                    if cell._tc not in seen:
                        seen.add(cell._tc)
                        yield from docx_blocks(cell, links, blocks)
