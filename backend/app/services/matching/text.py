"""The same bounded, allowlisted representation for both documents."""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.schemas.matching import FeatureContribution
from app.services.matching.safety import ASPIRATION, NEGATION

TASKS = {
    "build": r"\b(?:build|built|building|develop|developed|developing|development)\b",
    "test": r"\b(?:test|tests|testing|tested)\b",
    "deploy": r"\b(?:deploy|deployed|deploying|deployment)\b",
    "maintain": r"\b(?:maintain|maintained|maintaining|maintenance)\b",
    "design": r"\b(?:design|designed|designing)\b",
    "backend": r"\b(?:backend|back-end)\b",
    "frontend": r"\b(?:frontend|front-end)\b",
    "pipeline": r"\b(?:pipeline|pipelines)\b",
    "api": r"\b(?:api|apis)\b",
    "automate": r"\b(?:automate|automated|automation)\b",
    "document": r"\b(?:document|documented|documentation)\b",
    "analyze": r"\b(?:analyze|analyse|analyzed|analysed|analyzing|analysing)\b",
}
PATTERNS = {name: re.compile(pattern, re.I) for name, pattern in TASKS.items()}


def scoring_tokens(units, skill_data, ontology):
    """No arbitrary words, names, dates, locations or personal attributes enter TF-IDF."""
    tokens, labels = set(), {}
    for index, definition in enumerate(ontology.skills):
        if definition.name in skill_data:
            token = f"skill_{index}"
            tokens.add(token)
            labels[token] = (definition.name, "skill")
    positions = [e for data in skill_data.values() for e in data["evidence"]]
    for unit in units:
        # Duty words on a name/company-only line cannot affect similarity. Only
        # local professional text tied to accepted ontology evidence contributes.
        if not any(unit.start <= e.start and e.end <= unit.start + len(unit.text) for e in positions):
            continue
        if NEGATION.search(unit.text) or ASPIRATION.search(unit.text):
            continue
        for name, pattern in PATTERNS.items():
            if pattern.search(unit.text):
                token = "task_" + name
                tokens.add(token)
                labels[token] = (name, "task")
    return " ".join(sorted(tokens)), labels


def text_similarity(resume, job, labels):
    if not resume or not job:
        return 0.0, []
    # Fit together for a consistent shared feature space. No cross-candidate state.
    vectorizer = TfidfVectorizer(tokenizer=str.split, token_pattern=None, lowercase=False,
                                 binary=True, smooth_idf=True, use_idf=True, norm="l2")
    matrix = vectorizer.fit_transform([resume, job])
    similarity = float(cosine_similarity(matrix[0], matrix[1])[0, 0])
    products = matrix[0].multiply(matrix[1]).tocoo()
    names = vectorizer.get_feature_names_out()
    contributions = [FeatureContribution(feature=labels[names[column]][0], kind=labels[names[column]][1],
                                         cosine_contribution=min(1.0, float(value)))
                     for column, value in zip(products.col, products.data)]
    contributions.sort(key=lambda item: (-item.cosine_contribution, item.feature))
    return min(100.0, max(0.0, 100 * similarity)), contributions
