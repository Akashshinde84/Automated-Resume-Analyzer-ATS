"""Conservative section-local record heuristics, with raw evidence retained."""
import re

from app.schemas.candidate import Certification, Education, Project, WorkExperience
from app.services.extraction.contacts import evidence, urls
from app.services.extraction.dates import DATE, RANGE, canonical, date_range, strip_dates

UNIVERSITY = re.compile(r"\b(?:university|université|universidad|universität|college|institute|polytechnic|school|iit|nit)\b|大学|विद्यालय", re.I)
DEGREE = re.compile(
    r"\b(?:Bachelor(?:['\u2019]s)?(?: of (?:Science|Arts|Engineering|Technology|Commerce|Business Administration))?"
    r"|Master(?:['\u2019]s)?(?: of (?:Science|Arts|Engineering|Technology|Commerce|Business Administration))?"
    r"|Doctor of Philosophy|Associate(?:['\u2019]s)?(?: of (?:Science|Arts))?|Ph\.?D\.?"
    r"|B\.?Sc\.?|M\.?Sc\.?|B\.S\.?|M\.S\.?|B\.A\.?|M\.A\.?|B\.?Tech\.?|M\.?Tech\.?|B\.?Eng\.?|M\.?Eng\.?|B\.?E\.?|M\.?E\.?|MBA|BBA|BCA|MCA|BA|MA|Diploma)\b", re.I)
TITLE = re.compile(r"\b(?:engineer|developer|analyst|manager|consultant|intern|scientist|researcher|architect|designer|director|officer|specialist|professor|technician|lead)\b", re.I)
COMPANY = re.compile(r"\b(?:inc\.?|ltd\.?|llc|corporation|corp\.?|technologies|solutions|labs|systems|limited|gmbh|plc)\b", re.I)
ACTION = re.compile(r"^(?:built|developed|led|managed|worked|created|implemented|responsible|collaborated|designed|improved|delivered|used)\b", re.I)


def parts(line):
    return [p.strip(" ,;–—") for p in re.split(r"\s*\|\s*|\s+at\s+", line) if p.strip()]


def explicit(line, label):
    match = re.match(rf"(?:{label})\s*:\s*(.+)", line, re.I)
    return match[1].strip() if match else None


def short_header(line):
    return bool(line and not line.startswith("-") and len(line) <= 140
                and len(line.split()) <= 18 and not ACTION.search(line))


def title_in(line):
    for part in parts(strip_dates(line)):
        value = explicit(part, "job title|title|role")
        if value:
            return value
        if short_header(part) and TITLE.search(part) and not UNIVERSITY.search(part):
            return part.strip(" ,-")
    return None


def company_in(line, entities):
    candidates = []
    for part in parts(strip_dates(line)):
        value = explicit(part, "company|employer|organization")
        if value:
            candidates.append((value, "heuristic", "explicit_company_label"))
        elif short_header(part) and not TITLE.search(part) and COMPANY.search(part):
            candidates.append((part, "heuristic", "company_suffix"))
        else:
            matches = {e.text for e in entities if e.label == "ORG" and e.text in part}
            if short_header(part) and not TITLE.search(part) and len(matches) == 1:
                entity = next(iter(matches))
                if part == entity or part.startswith(entity + ","):
                    candidates.append((entity, "pretrained_ner", "section_local_unique_org"))
    # Two organizations in one header do not establish which is the employer.
    unique = {candidate[0] for candidate in candidates}
    return candidates[0] if len(unique) == 1 else (None, None, None)


def education_records(text):
    blocks, lines = [], []
    has_institution = has_degree = False
    for line in text.splitlines():
        if not line.strip():
            continue
        institution = bool(UNIVERSITY.search(line) or explicit(line, "institution|school")) and short_header(line)
        degree = bool(DEGREE.search(line)) and short_header(line)
        if lines and ((institution and has_institution) or (degree and has_degree)):
            blocks.append("\n".join(lines))
            lines = []
            has_institution = has_degree = False
        lines.append(line)
        has_institution |= institution
        has_degree |= degree
    if lines:
        blocks.append("\n".join(lines))
    result = []
    for block in blocks:
        record = Education(raw_text=block)
        for line in block.splitlines():
            for part in parts(line):
                clean = strip_dates(part)
                institution = explicit(clean, "institution|school")
                if institution or (UNIVERSITY.search(clean) and not DEGREE.search(clean) and short_header(clean)):
                    if record.institution is None:
                        record.institution = institution or clean
                        record.provenance.append(evidence("institution", "heuristic", "university_vocabulary_or_label", part))
                match = DEGREE.search(clean)
                if match and record.degree is None:
                    record.degree = match.group().rstrip(".")
                    record.provenance.append(evidence("degree", "heuristic", "explicit_degree_vocabulary", match.group(), "high"))
                    tail = clean[match.end():].strip(" .,:;()-")
                    field = re.match(r"(?:in|of|major(?:ing)? in)\s+(.+)", tail, re.I)
                    if field:
                        record.field = field[1].strip(" ,;")
                        record.provenance.append(evidence("field", "heuristic", "degree_field_connector", field.group()))
                    elif re.fullmatch(r"(?:Computer Science|Data Science|Information Technology|Physics|Mathematics|Chemistry|History|Economics|Mechanical Engineering|Electrical Engineering|Civil Engineering)", tail, re.I):
                        record.field = tail
                        record.provenance.append(evidence("field", "heuristic", "known_field_after_degree", tail))
                major = explicit(clean, "field|major|specialization")
                if major:
                    record.field = major
                    record.provenance.append(evidence("field", "heuristic", "explicit_field_label", part, "high"))
        start, end, source = date_range(block)
        if source:
            record.start_date, record.end_date = start, end
            record.provenance.append(evidence("dates", "regex", "explicit_date_range", source, "high"))
        else:
            dates = DATE.findall(block)
            if len(dates) == 1:
                if re.search(r"\b(?:graduated|graduation|completed|awarded)\b", block, re.I):
                    record.end_date = canonical(dates[0])
                    record.provenance.append(evidence("end_date", "heuristic", "explicit_completion_date", dates[0]))
                else:
                    record.warnings.append("An unlabeled education date is ambiguous; structured dates remain null.")
        if not record.institution or not record.degree:
            record.warnings.append("Education fields without sufficient evidence remain null.")
        result.append(record)
    return result


def experience_records(text, entities):
    blocks, lines = [], []
    has_company = has_title = has_dates = False
    for line in text.splitlines():
        if not line.strip():
            continue
        is_header = short_header(line)
        company = bool(company_in(line, entities)[0]) if is_header else False
        title = bool(title_in(line)) if is_header else False
        dates = bool(RANGE.search(line)) and not line.startswith("-")
        if lines and ((company and has_company) or (title and has_title) or (dates and has_dates)):
            blocks.append("\n".join(lines))
            lines = []
            has_company = has_title = has_dates = False
        lines.append(line)
        has_company |= company
        has_title |= title
        has_dates |= dates
    if lines:
        blocks.append("\n".join(lines))
    result = []
    for block in blocks:
        record = WorkExperience(raw_text=block)
        descriptions = []
        for line in block.splitlines():
            title = title_in(line) if short_header(line) else None
            company, method, rule = company_in(line, entities) if short_header(line) else (None, None, None)
            if title and not record.job_title:
                record.job_title = title
                record.provenance.append(evidence("job_title", "heuristic", "role_vocabulary_or_label", line))
            if company and not record.company:
                record.company = company
                record.provenance.append(evidence("company", method, rule, company, None if method == "pretrained_ner" else "medium"))
            if not title and not company and not RANGE.search(line):
                descriptions.append(line)
        record.start_date, record.end_date, source = date_range(block)
        if source:
            record.provenance.append(evidence("dates", "regex", "explicit_date_range", source, "high"))
        record.description = "\n".join(descriptions).strip() or None
        if not record.company or not record.job_title:
            record.warnings.append("Company or job title is missing or ambiguous; inspect raw_text.")
        result.append(record)
    return result


def item_blocks(text, label):
    blocks, lines = [], []
    for line in text.splitlines():
        if not line:
            continue
        labeled = explicit(line, label)
        # Only clear headers create boundaries; bullet descriptions stay attached.
        header = labeled or (short_header(line) and not line.lower().startswith(("issuer:", "date:", "credential", "issued by"))
                             and not DATE.fullmatch(line) and not line.startswith(("http", "www.")))
        if header and lines:
            blocks.append("\n".join(lines))
            lines = []
        lines.append(line)
    if lines:
        blocks.append("\n".join(lines))
    return blocks


def project_records(text):
    result = []
    for block in item_blocks(text, "project(?: name)?"):
        lines = block.splitlines()
        first = lines[0]
        name = explicit(first, "project(?: name)?") or parts(first)[0].lstrip("- ")
        if urls(name) == [name] or name.startswith(("http://", "https://")):
            name = None
        result.append(Project(name=name, description="\n".join(lines[1:]).strip() or None,
                              urls=urls(block), raw_text=block,
                              provenance=[evidence("name", "heuristic", "project_section_header", first, "low")] if name else []))
    return result


def certification_records(text):
    result = []
    for block in item_blocks(text, "certification|certificate"):
        first = block.splitlines()[0]
        name = explicit(parts(first)[0], "certification|certificate") or strip_dates(parts(first)[0]).lstrip("- ") or None
        record = Certification(name=name, raw_text=block)
        if name:
            record.provenance.append(evidence("name", "heuristic", "certification_section_header", first, "low"))
        for line in block.splitlines():
            for part in parts(line):
                issuer = explicit(part, "issuer|issued by")
                credential = explicit(part, "credential id|credential|certificate id")
                if issuer:
                    record.issuer = issuer
                    record.provenance.append(evidence("issuer", "heuristic", "explicit_issuer_label", part, "high"))
                if credential:
                    record.credential_id = credential
                    record.provenance.append(evidence("credential_id", "regex", "explicit_credential_label", part, "high"))
        dates = DATE.findall(block)
        if len(dates) == 1:
            record.date = canonical(dates[0])
            record.provenance.append(evidence("date", "regex", "single_certification_date", dates[0]))
        elif dates:
            record.warnings.append("Multiple certification dates found; date remains null.")
        result.append(record)
    return result
