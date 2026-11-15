"""Explicit, partial-precision date parsing; no imputed months or days."""
import re

MONTHS = {name: index for index, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
TOKEN = rf"(?:{MONTH}\s+(?:19|20)\d{{2}}|(?:19|20)\d{{2}}-(?:0[1-9]|1[0-2])|(?:0?[1-9]|1[0-2])/(?:19|20)\d{{2}}|(?:19|20)\d{{2}})"
DATE = re.compile(rf"(?<![\w/]){TOKEN}(?![\w/])", re.I)
RANGE = re.compile(rf"(?<!\w)({TOKEN})\s*(?:[-–—]|\bto\b)\s*({TOKEN}|present|current|now)\b", re.I)


def canonical(value: str) -> str:
    value = value.strip()
    if value.casefold() in {"present", "current", "now"}:
        return "present"
    match = re.fullmatch(rf"({MONTH})\s+((?:19|20)\d{{2}})", value, re.I)
    if match:
        return f"{match[2]}-{MONTHS[match[1][:3].lower()]:02d}"
    if "/" in value:
        month, year = value.split("/")
        return f"{year}-{int(month):02d}"
    return value


def date_range(text: str):
    match = RANGE.search(text)
    return (canonical(match[1]), canonical(match[2]), match.group()) if match else (None, None, None)


def strip_dates(text: str) -> str:
    return DATE.sub("", RANGE.sub("", text)).strip(" ,;|–—-")
