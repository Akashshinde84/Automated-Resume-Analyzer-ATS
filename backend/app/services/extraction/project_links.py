"""Classify only evidenced project links; leave conflicting candidates unresolved."""
import re
from urllib.parse import urlsplit

from app.services.document_links import normalize_url


def finalize_project(project):
    project.urls = list(dict.fromkeys(url for raw in project.urls if (url := normalize_url(raw))))
    github, live = [], []
    for url in project.urls:
        parsed = urlsplit(url)
        if parsed.hostname in {"github.com", "www.github.com"}:
            if len(parsed.path.strip("/").split("/")) >= 2:
                github.append(url)
        elif parsed.hostname not in {"linkedin.com", "www.linkedin.com"}:
            labeled = any(re.search(r"\b(?:demo|live|website)\b", line, re.I) and url in line
                          for line in project.raw_text.splitlines())
            labeled |= any(re.search(r"\b(?:demo|live|website)\b", e.source_text.split(" -> ")[0], re.I)
                           and e.source_text.endswith(" -> " + url) for e in project.provenance)
            if labeled:
                live.append(url)
    project.github_url = github[0] if len(github) == 1 else None
    project.live_url = live[0] if len(live) == 1 else None
    for label, values in (("GitHub repository", github), ("live demo", live)):
        if len(values) > 1:
            project.warnings.append(f"Multiple {label} links found; the primary URL remains null. Review all evidenced links.")
    project.warnings = list(dict.fromkeys(project.warnings))
    project.evidence = list(project.provenance)
    project.extraction_warnings = list(project.warnings)
    return project
