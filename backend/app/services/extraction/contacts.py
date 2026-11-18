"""Contact rules: never infer a phone region or follow any extracted URL."""
import re
from urllib.parse import urlsplit, urlunsplit

import phonenumbers

from app.schemas.candidate import Evidence, PhoneNumber
from app.services.extraction.dates import RANGE
from app.services.document_links import URL, visible_urls

EMAIL = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@(?:[\w-]+\.)+[\w-]{2,63}", re.UNICODE)
PHONE = re.compile(r"\+?\d[\d ().-]{5,}\d(?:\s*(?:ext\.?|x)\s*\d+)?", re.I)
PHONE_LABEL = re.compile(r"\b(?:phone|mobile|tel(?:ephone)?|cell|contact number)\s*[:.]?\s*", re.I)


def evidence(field, method, rule, source, confidence="medium"):
    return Evidence(field=field, method=method, rule=rule, source_text=source, confidence=confidence)


def urls(text: str) -> list[str]:
    return visible_urls(text)


def extract_contacts(text: str, region: str | None):
    emails = []
    phones = []
    linkedin, github, portfolios = [], [], []
    provenance = []
    warnings = []
    for match in EMAIL.finditer(text):
        local, domain = match.group().rstrip(".").rsplit("@", 1)
        value = local + "@" + domain.lower()
        if value not in emails:
            emails.append(value)
            provenance.append(evidence("emails", "regex", "email_syntax_not_delivery_verified", match.group(), "high"))
    seen = set()
    for line in text.splitlines():
        for value in urls(line):
            parsed = urlsplit(value)
            host = (parsed.hostname or "").removeprefix("www.")
            path = parsed.path.strip("/")
            if host == "linkedin.com" and path.startswith(("in/", "pub/")):
                target, field = linkedin, "linkedin_urls"
            elif host == "github.com" and path and path.split("/")[0].lower() not in {"features", "topics", "about", "orgs", "settings", "login"}:
                target, field = github, "github_urls"
            elif host not in {"linkedin.com", "github.com"} and (
                re.search(r"\b(?:portfolio|website|personal site)\s*[:|]", line, re.I) or host.endswith(".github.io")
            ):
                target, field = portfolios, "portfolio_urls"
            else:
                continue
            if value not in target:
                target.append(value)
                provenance.append(evidence(field, "regex", "contact_url_host_or_explicit_label", value))
        label = PHONE_LABEL.search(line)
        candidates = list(PHONE.finditer(line))
        for match in candidates:
            raw = match.group().strip()
            if RANGE.fullmatch(raw):
                continue
            # No IDs/date ranges or numbers embedded in email/URL text.
            protected = list(EMAIL.finditer(line)) + list(URL.finditer(line))
            if any(match.start() < item.end() and item.start() < match.end() for item in protected):
                continue
            if not (raw.startswith("+") or label or PHONE.fullmatch(line.strip())):
                continue
            digits = re.sub(r"\D", "", raw)
            if not 7 <= len(digits) <= 22:
                continue
            number = None
            status = "ambiguous"
            if raw.startswith("+") or region:
                try:
                    number = phonenumbers.parse(raw, region)
                    status = "valid" if phonenumbers.is_valid_number(number) else "invalid"
                except phonenumbers.NumberParseException:
                    status = "invalid"
            e164 = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164) if status == "valid" else None
            extension = number.extension if number else None
            key = (e164 or raw, extension)
            if key in seen:
                continue
            seen.add(key)
            phones.append(PhoneNumber(raw=raw, e164=e164, extension=extension,
                                      region=phonenumbers.region_code_for_number(number) if status == "valid" else None,
                                      status=status))
            provenance.append(evidence("phones", "phone_library" if status != "ambiguous" else "regex",
                                       "libphonenumber_validation" if status != "ambiguous" else "national_number_without_region", raw,
                                       "high" if status == "valid" else "low"))
            if status == "ambiguous":
                warnings.append("A national phone number lacks an explicit region; its E.164 value is null.")
            elif status == "invalid":
                warnings.append("A phone-like value failed library validation; its E.164 value is null.")
    return dict(emails=emails, phones=phones, linkedin_urls=linkedin, github_urls=github,
                portfolio_urls=portfolios, provenance=provenance), list(dict.fromkeys(warnings))
