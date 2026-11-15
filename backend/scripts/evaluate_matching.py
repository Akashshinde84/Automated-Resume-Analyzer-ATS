"""Reproduce the small, annotated synthetic diagnostic evaluation; no training."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services.matching import MatchingService


def evaluate():
    pairs = json.loads((ROOT / 'docs/evaluation/matching_pairs.json').read_text(encoding='utf-8'))['pairs']
    service = MatchingService()
    rows = []
    for pair in pairs:
        result = service.match(pair['request']['resume'], pair['request']['job_description'])
        actual = {
            'required': [s.name for s in result.required_skills],
            'preferred': [s.name for s in result.preferred_skills],
            'matched': [s.name for s in result.matched_skills],
            'missing_required': [s.name for s in result.missing_required_skills],
            'skill_overlap': result.scores.skill_overlap, 'status': result.status,
        }
        rows.append({'id': pair['id'], 'annotations_pass': actual == pair['expected'],
                     'actual': actual, 'scores': result.scores.model_dump()})
    return rows


if __name__ == '__main__':
    rows = evaluate()
    passed = sum(row['annotations_pass'] for row in rows)
    (ROOT / 'docs/evaluation/matching_results.json').write_text(json.dumps({'annotation_checks_passed':passed,'cases':len(rows),'results':rows},indent=2)+'\n',encoding='utf-8')
    lines = ['# Synthetic matching evaluation', '',
             f'{passed}/{len(rows)} handwritten diagnostic cases match their annotated skill sets, status and overlap score.', '',
             '| Case | Skill overlap | Lexical similarity | Overall | Annotation check |',
             '| --- | ---: | ---: | ---: | --- |']
    for row in rows:
        s=row['scores']
        lines.append(f"| {row['id']} | {s['skill_overlap']} | {s['text_similarity']} | {s['overall']} | {'pass' if row['annotations_pass'] else 'FAIL'} |")
    lines += ['', 'Scores are project-defined estimates, not ATS scores or hiring probabilities. None means unavailable.', '',
              'This hand-authored set exercises expected behavior, not generalization. It has no hiring outcomes, independent real-world test corpus, demographic coverage, measured fairness, or calibration. Passing these cases is not an accuracy claim.', '',
              'Reproduce: `backend/.venv/Scripts/python.exe backend/scripts/evaluate_matching.py` from the repository root.', '']
    (ROOT / 'docs/evaluation/matching_results.md').write_text('\n'.join(lines),encoding='utf-8')
    print(f'{passed}/{len(rows)} annotated cases passed')
    raise SystemExit(0 if passed == len(rows) else 1)
