"""Diagnostic ranking against explicit developer labels, not human evaluation."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services.matching import MatchingService

def strict_pairs(scores, order):
    pairs = [(a,b) for index,a in enumerate(order) for b in order[index+1:]]
    return sum(scores[a] is not None and scores[b] is not None and scores[a] > scores[b] for a,b in pairs)


def main():
    dataset = json.loads((ROOT / 'docs/evaluation/matching_relevance.json').read_text(encoding='utf-8'))
    service = MatchingService()
    rows = []
    for query in dataset['queries']:
        scores = {label: service.match({'text': query[label]}, query['job']).scores.overall for label in dataset['expected_order']}
        ordered = sorted(scores, key=lambda label: scores[label] if scores[label] is not None else -1, reverse=True)
        checked = strict_pairs(scores, dataset['expected_order'])
        rows.append({'id': query['id'], 'scores': scores, 'order': ordered, 'passed_pairs': checked, 'passes': checked == 3})
    result = {'label_source': dataset['label_source'], 'queries': len(rows), 'pairwise_order_checks': len(rows)*3,
              'passed_pairs': sum(row['passed_pairs'] for row in rows),
              'passed_queries': sum(row['passes'] for row in rows), 'results': rows, 'limitations': dataset['limitations']}
    (ROOT / 'docs/evaluation/relevance_results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(f"{result['passed_queries']}/{len(rows)} developer-labeled ranking queries passed; no human relevance accuracy claim.")
    return 0 if all(row['passes'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
