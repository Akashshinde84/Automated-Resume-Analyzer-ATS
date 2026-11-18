"""Conservative section-local record heuristics, with raw evidence retained."""
import re

from app.schemas.candidate import Activity, Certification, Education, Project, WorkExperience
from app.services.extraction.contacts import evidence, urls
from app.services.extraction.dates import DATE, RANGE, canonical, date_range, strip_dates

UNIVERSITY = re.compile(r"\b(?:university|université|universidad|universität|college|institute|polytechnic|school|iit|nit)\b|大学|विद्यालय", re.I)
DEGREE = re.compile(
    r"\b(?:Bachelor(?:['\u2019]s)?(?: of (?:Science|Arts|Engineering|Technology|Commerce|Business Administration))?"
    r"|Master(?:['\u2019]s)?(?: of (?:Science|Arts|Engineering|Technology|Commerce|Business Administration))?"
    r"|Doctor of Philosophy|Associate(?:['\u2019]s)?(?: of (?:Science|Arts))?|Ph\.?D\.?"
    r"|B\.?Sc\.?|M\.?Sc\.?|B\.S\.?|M\.S\.?|B\.A\.?|M\.A\.?|B\.?Tech\.?|M\.?Tech\.?|B\.?Eng\.?|M\.?Eng\.?|B\.?E\.?|M\.?E\.?|MBA|BBA|BCA|MCA|BA|MA|Diploma|HSC|SSC|Higher Secondary(?: Certificate)?|Secondary School Certificate|Class XII|Class X)\b", re.I)
TITLE = re.compile(r"\b(?:engineer|developer|analyst|manager|consultant|intern|scientist|researcher|architect|designer|director|officer|specialist|professor|technician|lead)\b", re.I)
COMPANY = re.compile(r"\b(?:inc\.?|ltd\.?|llc|corporation|corp\.?|technologies|solutions|labs|systems|limited|gmbh|plc)\b", re.I)
ACTION = re.compile(r"^(?:built|developed|led|managed|worked|created|implemented|responsible|collaborated|designed|improved|delivered|used|integrated|utilized|achieved|enabled|automated|deployed|supports|provides|uses|a |an |the )\b", re.I)


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


def education_records(text, entities=()):
    blocks, lines = [], []
    has_institution = has_degree = False
    for line in text.splitlines():
        if not line.strip():
            continue
        institution = bool(UNIVERSITY.search(line) or explicit(line, "institution|school")) and short_header(line)
        degree = bool(DEGREE.search(line)) and short_header(line)
        if lines and ((institution and has_institution and has_degree) or (degree and has_degree)):
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
                    elif re.fullmatch(r"(?:AI\s*&\s*ML|Artificial Intelligence(?:\s*(?:and|&)\s*Machine Learning)?|Computer Engineering)", tail, re.I):
                        record.field = tail
                        record.provenance.append(evidence("field", "heuristic", "explicit_specialization_after_degree", tail))
                    prefix = clean[:match.start()].strip(" ,;|:-")
                    if not record.institution and UNIVERSITY.search(prefix):
                        record.institution = prefix
                        record.provenance.append(evidence("institution", "heuristic", "institution_before_degree", prefix))
                major = explicit(clean, "field|major|specialization")
                if major:
                    record.field = major
                    record.provenance.append(evidence("field", "heuristic", "explicit_field_label", part, "high"))
                grade = re.search(r"\b(?:CGPA|GPA|percentage|grade|score)\s*[:=-]?\s*\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?|\s*%)?", part, re.I)
                if grade:
                    record.grade = grade.group()
                    record.provenance.append(evidence("grade", "regex", "explicit_grade_label", grade.group(), "high"))
                if record.field is None and re.fullmatch(r"(?:AI\s*&\s*ML|Artificial Intelligence(?:\s*(?:and|&)\s*Machine Learning)?|Computer Science|Computer Engineering|Information Technology)", clean, re.I):
                    record.field = clean
                    record.provenance.append(evidence("field", "heuristic", "separate_specialization_line", clean))
        if not record.institution and record.degree:
            candidates = [e.text for e in entities if e.label == "ORG" and e.text in block.splitlines() and not DEGREE.search(e.text)]
            if len(set(candidates)) == 1:
                record.institution = candidates[0]
                record.provenance.append(evidence("institution", "pretrained_ner", "unique_education_org_line", candidates[0], None))
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


LINK_LABEL = re.compile(r"^\[?(?:github|linkedin|link|demo|live demo|source(?: code)?|repository|certificate|credential link)\]?$", re.I)
METADATA = re.compile(r"^(?:technologies|tech(?:nology)? stack|stack|tools|issuer|issued by|date|credential(?: id| link)?|certificate id)\s*:", re.I)
MONTH_ONLY = re.compile(r"^(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?$", re.I)
DESCRIPTION = re.compile(r"\b(?:that|which|using|utilizing|allows|enables|provides|supports|designed to|users can)\b|^(?:features? include|includes|offers|handles|ensures|processes|integrates|generates|collects|fetches|displays|stores|validates|reduces|increases|improves)\b", re.I)
ISSUERS = {value.casefold(): value for value in ("Siemens", "Persevex", "Forage", "NPTEL", "Coursera", "edX", "Udemy", "Microsoft", "Google", "AWS", "Cisco", "IBM")}


def title_candidate(line, label, title_hints=()):
    clean = line.lstrip('- ').strip()
    labeled = explicit(clean, label)
    if labeled:
        return labeled
    if (not clean or LINK_LABEL.fullmatch(clean) or re.match(r"^(?:github|demo|live(?: demo)?|repository|source(?: code)?|website)\s*:", clean, re.I) or METADATA.search(clean)
            or DATE.fullmatch(clean) or MONTH_ONLY.fullmatch(clean) or urls(clean) == [clean]
            or clean.lower().startswith(('http', 'www.')) or ACTION.search(clean)
            or DESCRIPTION.search(clean)):
        return None
    if re.match(r"^(?:issued|completed|awarded)\b", clean, re.I) or (DATE.search(clean) and not strip_dates(clean)):
        return None
    if clean in title_hints and len(clean) < 160:
        return clean
    if not short_header(clean) or len(clean.split()) > 10 or clean.endswith(('.', ';')):
        return None
    if clean[0].islower() or re.search(r'[.!?]\s+\w', clean):
        return None
    return clean


def bare_stack(line):
    from app.services.skills import get_skill_extractor
    stack = get_skill_extractor().extract('Skills\n' + line)
    remaining = line
    for span in sorted((span for skill in stack for span in skill.occurrences), key=lambda span: span.start, reverse=True):
        start, end = span.start - len('Skills\n'), span.end - len('Skills\n')
        remaining = remaining[:start] + ' ' * (end-start) + remaining[end:]
    return bool(stack) and not remaining.strip(' ,;|/+-& ')


def item_blocks(text, label, title_hints=()):
    blocks, lines = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        title = title_candidate(line, label, title_hints)
        if title and lines and label == 'project(?: name)?':
            # A bare stack beneath a title is supporting metadata, not a project.
            if bare_stack(line):
                title = None
        if "certification" in label and lines and line.casefold() in ISSUERS:
            title = None
        # Bullet descriptions cannot become titles merely because they are short.
        if line.startswith('-') and not explicit(line.lstrip('- '), label):
            title = None
        if title and lines:
            blocks.append('\n'.join(lines)); lines = []
        if title or lines:
            lines.append(line)
    if lines:
        blocks.append('\n'.join(lines))
    return blocks


def descriptions(lines):
    result = []
    for line in lines:
        if LINK_LABEL.fullmatch(line) or METADATA.search(line) or urls(line) == [line] or DATE.fullmatch(line) or MONTH_ONLY.fullmatch(line):
            continue
        if result and not line.startswith('-'):
            result[-1] += ' ' + line
        else:
            result.append(line)
    return '\n'.join(result).strip() or None


def project_records(text, title_hints=()):
    from app.services.skills import get_skill_extractor
    from app.services.extraction.project_links import finalize_project
    result = []
    for block in item_blocks(text, 'project(?: name)?', title_hints):
        lines = block.splitlines()
        first = lines[0]
        name = explicit(first.lstrip('- '), 'project(?: name)?') or parts(first)[0].lstrip('- ')
        name = re.sub(r'\s*\[(?:GitHub|Demo|Link)\].*$', '', name, flags=re.I).strip()
        if not name or LINK_LABEL.fullmatch(name):
            continue
        stack_lines = [line.split(':', 1)[1] for line in lines if re.match(r'^(?:technologies|tech(?:nology)? stack|stack|tools)\s*:', line, re.I)]
        stack_lines.extend(line for line in lines[1:] if bare_stack(line))
        if '|' in first:
            stack_lines.extend(parts(first)[1:])
        skills = get_skill_extractor().extract(block)
        if stack_lines:
            skills += get_skill_extractor().extract('Skills\n' + '\n'.join(stack_lines))
        technologies = list(dict.fromkeys(s.name for s in skills))
        result.append(Project(name=name, description=descriptions(lines[1:]),
                              technologies=technologies, urls=urls(block), raw_text=block,
                              provenance=[evidence('name', 'heuristic', 'project_header_with_continuations', first)]))
    return [finalize_project(project) for project in result]


def certification_records(text, title_hints=()):
    result = []
    for block in item_blocks(text, 'certification|certificate', title_hints):
        first = block.splitlines()[0]
        name = explicit(parts(first)[0].lstrip('- '), 'certification|certificate') or strip_dates(parts(first)[0]).lstrip('- ')
        if not name or LINK_LABEL.fullmatch(name):
            continue
        record = Certification(name=name, raw_text=block, urls=urls(block),
                               description=descriptions(block.splitlines()[1:]))
        record.provenance.append(evidence('name', 'heuristic', 'certification_header_with_continuations', first))
        for line in block.splitlines():
            for part in parts(line):
                issuer = explicit(part, 'issuer|issued by')
                credential = explicit(part, 'credential id|certificate id')
                if issuer:
                    record.issuer = issuer
                    record.provenance.append(evidence('issuer', 'heuristic', 'explicit_issuer_label', part, 'high'))
                if credential:
                    record.credential_id = credential
                    record.provenance.append(evidence('credential_id', 'regex', 'explicit_credential_label', part, 'high'))
        if not record.issuer and len(block.splitlines()) > 1:
            issuer_line = block.splitlines()[1]
            if issuer_line.casefold() in ISSUERS:
                record.issuer = issuer_line
                record.provenance.append(evidence('issuer', 'heuristic', 'standalone_adjacent_publisher', issuer_line))
        if not record.issuer:
            match = re.search(r'\s+(?:by|from)\s+(.+?)(?:\s*\||$)', strip_dates(first), re.I)
            if match:
                record.issuer = match[1].strip(' ,;-')
                record.name = re.split(r'\s+(?:by|from)\s+', record.name, flags=re.I)[0]
                record.provenance.append(evidence('issuer', 'heuristic', 'explicit_issuer_connector', match.group()))
        date_text = re.sub(r'([A-Za-z]{3,9})\.?\n((?:19|20)\d{2})', r'\1 \2', block)
        dates = DATE.findall(date_text)
        if len(dates) == 1:
            record.date = canonical(dates[0])
            record.provenance.append(evidence('date', 'regex', 'single_certification_date', dates[0]))
        elif dates:
            record.warnings.append('Multiple certification dates found; date remains null.')
        result.append(record)
    return result


def activity_records(text):
    return [Activity(name=None, description=text.strip(), raw_text=text)] if text.strip() else []
