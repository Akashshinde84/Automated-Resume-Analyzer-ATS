"""Metrics must penalize extra predictions, missing labels and wrong empty fields."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('evaluate_nlp', Path(__file__).resolve().parents[1] / 'scripts/evaluate_nlp.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_precision_recall_and_f1_are_count_based():
    counts = evaluation.compare({'python','sql'}, {'python','java','go'})
    assert counts == {'tp':1,'fp':2,'fn':1}
    metrics = evaluation.metric(**counts)
    assert metrics['precision'] == pytest.approx(1/3)
    assert metrics['recall'] == .5
    assert metrics['f1'] == .4


def test_empty_undefined_metrics_are_not_fake_perfect_accuracy():
    assert evaluation.metric(0,0,0)['f1'] is None
    assert evaluation.metric(0,1,0)['precision'] == 0
    assert evaluation.metric(0,0,1)['recall'] == 0


def test_corpus_is_synthetic_unique_and_balanced_formats():
    import json
    corpus = json.loads(evaluation.DATASET.read_text(encoding='utf-8'))
    assert corpus['license'] == 'CC0-1.0'
    assert len({case['id'] for case in corpus['cases']}) == 20
    assert sum(case['format'] == 'pdf' for case in corpus['cases']) == 10
    assert sum(case['format'] == 'docx' for case in corpus['cases']) == 10


def test_ranking_ties_and_missing_scores_do_not_count_as_success():
    spec = importlib.util.spec_from_file_location('evaluate_relevance', Path(__file__).resolve().parents[1] / 'scripts/evaluate_relevance.py')
    relevance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(relevance)
    labels = ['full','partial','unrelated']
    assert relevance.strict_pairs({'full':100,'partial':50,'unrelated':0}, labels) == 3
    assert relevance.strict_pairs(dict.fromkeys(labels,0), labels) == 0
    assert relevance.strict_pairs(dict.fromkeys(labels,None), labels) == 0
