"""Normalize evidenced links only; never visit them or infer technology domains."""
import re
from urllib.parse import urlsplit, urlunsplit
from urllib.parse import unquote

URL = re.compile(r"(?<![@\w])(?:https?://[^\s<>\"]+|www\.[^\s<>\"]+|(?:linkedin\.com|github\.com)/[^\s<>\"]+)", re.I)


def normalize_url(raw):
    raw = raw.strip().rstrip(".,;:!?)\u3002]")
    if len(raw) > 2048:
        return None
    if not re.match(r"https?://", raw, re.I):
        if not re.match(r"(?:www\.|(?:linkedin\.com|github\.com)/)", raw, re.I):
            return None
        raw = "https://" + raw
    try:
        parsed = urlsplit(raw)
        if (parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname
                or "." not in parsed.hostname or parsed.username or parsed.password
                or any(c.isspace() or ord(c) < 32 for c in raw)):
            return None
        _ = parsed.port
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ""))
    except ValueError:
        return None


def visible_urls(text):
    return list(dict.fromkeys(value for match in URL.finditer(text) if (value := normalize_url(match.group()))))


def normalize_document_target(raw):
    if not isinstance(raw, str) or len(raw) > 2048 or any(ord(c) < 32 for c in raw):
        return None
    if raw.lower().startswith("mailto:"):
        address = unquote(raw[7:].split("?", 1)[0])
        return "mailto:" + address if re.fullmatch(r"[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+", address) else None
    if raw.lower().startswith("tel:"):
        number = unquote(raw[4:])
        return "tel:" + number if re.fullmatch(r"\+?[\d ().-]{7,30}", number) else None
    return normalize_url(raw)
