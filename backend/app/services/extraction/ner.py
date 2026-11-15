"""Pretrained model adapter, isolated from deterministic extraction rules."""
from functools import lru_cache
from threading import Lock

import spacy

from app.schemas.candidate import NamedEntity, NLPMetadata

_LOCK = Lock()


@lru_cache(maxsize=2)
def load_model(model: str):
    try:
        nlp = spacy.load(model, disable=["parser", "tagger", "lemmatizer", "attribute_ruler"])
    except OSError:
        return None
    return nlp if "ner" in nlp.pipe_names else None


class SpacyNER:
    def __init__(self, model: str = "en_core_web_sm"):
        self.model = model

    def analyze(self, text: str) -> tuple[list[NamedEntity], NLPMetadata, list[str]]:
        # Serialize shared inference/model initialization; no resume text is logged.
        with _LOCK:
            nlp = load_model(self.model)
            if nlp is None:
                return [], NLPMetadata(model=self.model, status="unavailable"), [
                    "Pretrained NER model unavailable; only regex and heuristics were used. Install the configured spaCy model."
                ]
            doc = nlp(text)
            entities = [NamedEntity(text=e.text, label=e.label_, start=e.start_char, end=e.end_char)
                        for e in doc.ents if e.label_ in {"PERSON", "ORG"}]
            metadata = NLPMetadata(model=self.model, model_version=nlp.meta.get("version"),
                                   status="available", language=nlp.lang)
        return entities, metadata, []
