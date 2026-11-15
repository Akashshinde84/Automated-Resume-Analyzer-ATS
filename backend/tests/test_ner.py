from importlib.util import find_spec

import pytest
import spacy
from spacy.tokens import Span

from app.services.extraction.ner import SpacyNER, load_model


def test_missing_model_is_explicit(monkeypatch):
    monkeypatch.setattr("app.services.extraction.ner.load_model", lambda name: None)
    entities, metadata, warnings = SpacyNER().analyze("Name: Jane Doe")
    assert entities == []
    assert metadata.status == "unavailable"
    assert warnings
    assert metadata.custom_trained is False


def test_adapter_offsets_and_null_scores(monkeypatch):
    # A manually annotated Doc tests the adapter, not pretrained model accuracy.
    nlp = spacy.blank("en")
    doc = nlp.make_doc("Jane Doe joined Example Labs.")
    doc.ents = [Span(doc, 0, 2, label="PERSON"), Span(doc, 3, 5, label="ORG")]
    class AnnotatedDoc:
        meta = {"version": "test"}
        lang = "en"
        def __call__(self, text):
            return doc
    monkeypatch.setattr("app.services.extraction.ner.load_model", lambda name: AnnotatedDoc())
    entities, metadata, _ = SpacyNER().analyze(doc.text)
    assert [entity.label for entity in entities] == ["PERSON", "ORG"]
    assert all(entity.text == doc.text[entity.start:entity.end] for entity in entities)
    assert all(entity.confidence is None for entity in entities)
    assert metadata.status == "available"


@pytest.mark.skipif(find_spec("en_core_web_sm") is None, reason="Official pretrained model not installed")
def test_real_pretrained_ner_smoke():
    entities, metadata, warnings = SpacyNER().analyze("Barack Obama worked at Microsoft in Seattle.")
    assert metadata.status == "available"
    assert metadata.model_version
    assert not warnings
    assert any(entity.label == "PERSON" for entity in entities)
    assert any(entity.label == "ORG" for entity in entities)
