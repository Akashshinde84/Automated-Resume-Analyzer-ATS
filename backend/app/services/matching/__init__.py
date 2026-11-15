"""Explainable, local resume-to-job compatibility estimate; no decision thresholds."""
import re

from app.schemas.matching import (
    Evidence, JobSkill, MatchingRequest, MatchingResponse, MatchingScores, MatchingWeights,
    SkillComparison, Suggestion,
)
from app.services.matching.job import job_units
from app.services.matching.safety import affirmative, resume_units
from app.services.matching.text import scoring_tokens, text_similarity
from app.services.skills import get_skill_extractor

FORMULA = "S=100*sum(importance_i*matched_i)/sum(importance_i); T=100*cosine(binary_TFIDF_resume,binary_TFIDF_job); overall=w_skills*S+w_text*T"


class MatchingService:
    def __init__(self, weights: MatchingWeights | None = None, skill_extractor=None):
        self.weights = weights if weights is not None else MatchingWeights()
        self.extractor = skill_extractor if skill_extractor is not None else get_skill_extractor()

    def _collect(self, units, resume):
        skills = {}
        warnings = []
        for unit in units:
            # Reuse ontology/context rules. Job requirement lists are skill-list context.
            prefix = "Skills: " if not resume or unit.section == "skills" else unit.section.title() + "\n"
            content = unit.text
            if not resume:
                # Mask explicit suffix markers without changing character positions.
                content = re.sub(r"\b(?:required|preferred|optional|essential|mandatory)\b", lambda m: " " * len(m.group()), content, flags=re.I)
            matches = self.extractor.extract(prefix + content)
            alternatives = not resume and len(matches) > 1 and bool(re.search(r"\bor\b", unit.text, re.I))
            if alternatives:
                warnings.append("Alternative skill requirements containing 'or' are left unspecified; review the employer's intended alternatives.")
            for skill in matches:
                for span in skill.occurrences:
                    start, end = span.start - len(prefix), span.end - len(prefix)
                    if not affirmative(unit.text, start, end, resume=resume):
                        warnings.append("Negated, not-required, or aspirational skill mentions were excluded from matching.")
                        continue
                    importance = "unspecified" if alternatives else unit.importance
                    if skill.name not in skills:
                        skills[skill.name] = {"category": skill.category, "evidence": [], "importance": set()}
                    entry = skills[skill.name]
                    entry["evidence"].append(Evidence(text=unit.text[start:end], start=unit.start + start,
                                                      end=unit.start + end,
                                                      section=unit.section if resume else importance,
                                                      context=unit.text[max(0, start - 100):end + 100]))
                    entry["importance"].add(importance)
        return skills, warnings

    def match(self, parsed_resume: dict, job_description: str,
              weights: MatchingWeights | None = None) -> MatchingResponse:
        payload = MatchingRequest(resume=parsed_resume, job_description=job_description, weights=weights)
        weights = payload.weights if payload.weights is not None else self.weights
        resume_text, job_text = payload.resume.text, payload.job_description
        resume_lines, excluded = resume_units(resume_text)
        job_lines, warnings = job_units(job_text)
        resume_skills, resume_warnings = self._collect(resume_lines, True)
        job_skills, job_warnings = self._collect(job_lines, False)
        warnings += resume_warnings + job_warnings
        if excluded:
            warnings.append("Personal or instruction-like resume clauses were excluded from scoring.")
        comparisons = []
        for name, data in job_skills.items():
            importance = next(kind for kind in ("required", "preferred", "unspecified") if kind in data["importance"])
            if len(data["importance"]) > 1:
                warnings.append("A skill has conflicting importance labels; required takes priority over preferred, then unspecified.")
            comparisons.append(SkillComparison(name=name, category=data["category"], importance=importance,
                                               job_evidence=data["evidence"], matched=name in resume_skills,
                                               resume_evidence=resume_skills[name]["evidence"] if name in resume_skills else []))
        required = [JobSkill(**s.model_dump(exclude={"matched", "resume_evidence"})) for s in comparisons if s.importance == "required"]
        missing = [JobSkill(**s.model_dump(exclude={"matched", "resume_evidence"})) for s in comparisons if s.importance == "required" and not s.matched]
        matched = [s for s in comparisons if s.matched]
        suggestions = []
        for skill in comparisons:
            if not skill.matched and skill.importance in {"required", "preferred"}:
                suggestions.append(Suggestion(code="review_requirement_gap" if skill.importance == "required" else "review_preferred_gap",
                    skill=skill.name, message=f"No qualifying resume evidence for {skill.name} was found. Review this job criterion against your actual background; do not list this skill without substantiating experience."))
            elif skill.matched and not any(e.section == "skills" for e in skill.resume_evidence):
                suggestions.append(Suggestion(code="surface_existing_evidence", skill=skill.name,
                    message=f"Your resume already mentions {skill.name}. If it reflects your experience, make that existing evidence easier to find in Skills and describe the work accurately; do not invent proficiency or outcomes.",
                    resume_evidence=skill.resume_evidence))
        scores = MatchingScores()
        status = "computed"
        effective = {"skills": weights.skills, "text": weights.text}
        features = []
        if not resume_text.strip() or not job_text.strip():
            status = "insufficient_input"
            effective = {"skills": 0.0, "text": 0.0}
            warnings.append("Empty resume or job text: scores are unavailable, not a rejection or a zero compatibility finding.")
        elif not comparisons:
            status = "no_supported_job_skills"
            effective = {"skills": 0.0, "text": 0.0}
            warnings.append("No supported affirmative job skills were found; no score is assigned. Unknown ontology skills cannot be assessed.")
        else:
            importance = {"required": weights.required_importance, "preferred": weights.preferred_importance,
                          "unspecified": weights.unspecified_importance}
            denominator = sum(importance[s.importance] for s in comparisons)
            overlap = 100 * sum(importance[s.importance] for s in matched) / denominator
            resume_repr, resume_labels = scoring_tokens(resume_lines, resume_skills, self.extractor.ontology)
            job_repr, job_labels = scoring_tokens(job_lines, job_skills, self.extractor.ontology)
            similarity, features = text_similarity(resume_repr, job_repr, resume_labels | job_labels)
            scores = MatchingScores(skill_overlap=round(overlap, 2), text_similarity=round(similarity, 2),
                                     overall=round(weights.skills * overlap + weights.text * similarity, 2))
            if not resume_skills:
                warnings.append("No affirmative ontology skill evidence was found in the included resume sections; missing evidence does not prove lack of ability.")
        warnings.extend([
            "Only ontology skills and allowlisted task terms in recognized professional sections enter scoring; contact/preamble and education institutions, names, dates, and personal attributes are not scoring features.",
            "TF-IDF is lexical similarity, not semantic understanding. Ontology coverage, section boundaries, negation and requirement rules are incomplete; review evidence manually.",
            "Unlabeled requirements stay unspecified. No automatic hiring/rejection decision or threshold is provided.",
        ])
        return MatchingResponse(status=status, scores=scores, weights=weights, effective_weights=effective,
            formula=FORMULA, ontology_version=self.extractor.ontology.version, required_skills=required,
            preferred_skills=[s for s in comparisons if s.importance == "preferred"],
            unspecified_skills=[s for s in comparisons if s.importance == "unspecified"], matched_skills=matched,
            missing_required_skills=missing, suggestions=suggestions, shared_text_features=features,
            warnings=list(dict.fromkeys(warnings)))
