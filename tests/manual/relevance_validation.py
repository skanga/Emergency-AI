#!/usr/bin/env python3
"""Run frozen follow-up cases without generating advice or claiming clinical accuracy."""
import argparse
import json
from pathlib import Path
from retrieval_eval import Engine, load_settings, evaluate_case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default=str(Path(__file__).with_suffix('.json')))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    cases = json.loads(Path(args.manifest).read_text(encoding='utf-8'))['cases']
    engine = Engine(load_settings())
    results = []
    for case in cases:
        result = evaluate_case(engine, case)
        expected = case['expected_topic']
        topics = result['retrieval']['topics']
        result['expected_topic'] = expected
        result['topic_match'] = expected in topics if expected else not topics
        results.append(result)
        print(case['id'] + ': completed', flush=True)
    summary = {'cases':len(results), 'topic_matches':sum(r['topic_match'] for r in results),
               'by_language':{}, 'source_applicability_review':'pending',
               'clinical_review':'not_performed', 'generated_answers':0}
    for lang in ('en','pt','es'):
        rows = [r for r in results if r['language'] == lang]
        summary['by_language'][lang] = {'matched':sum(r['topic_match'] for r in rows),'cases':len(rows)}
    Path(args.output).write_text(json.dumps({'summary':summary,'results':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
