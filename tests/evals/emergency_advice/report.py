"""Readable reports with explicit review coverage and separate quality dimensions."""
try:
    from . import suite
except ImportError:
    import suite


def assessment_text(review):
    if not review:
        return 'Unreviewed: no answer-quality conclusion.\n'
    lines = [f"Reviewer: {review['reviewer']}; method: {review['method']}; date: {review['reviewed_at']}.\n"]
    for dimension, item in review['assessments'].items():
        lines.append(f"- **{dimension}: {item['rating']}** — {item['reason']}")
        for evidence in item['evidence']:
            detail = evidence.get('quote') or evidence.get('observation', '')
            lines.append('  Evidence: ' + detail.replace('\n', ' ') +
                         '; references: ' + ', '.join(evidence.get('references', [])) +
                         '; supplied sources: ' + ', '.join(map(str, evidence.get('source_numbers', []))))
    return '\n'.join(lines) + '\n'


def overview(summary):
    lines = [f"Screening gate: **{summary['gate']}**. Reviewed {summary['reviewed']}/{summary['total']} answers.",
             'This is a scenario screen, not clinical certification. Unreviewed and uncertain answers cannot pass.',
             'First-token latency includes disclaimers; it is not time to useful advice.', '',
             '| Outcome | Cases |', '|---|---:|']
    lines += [f'| {k} | {v} |' for k, v in summary['outcomes'].items()]
    lines += ['', 'Ratings are separate; no combined quality score. Counts below cover reviewed answers only.', '']
    for dimension, counts in summary['ratings'].items():
        lines.append(f"- {dimension}: " + ', '.join(f'{k}={v}' for k, v in counts.items()))
    lines.append(f"\nInvalid numeric citation cases: {summary['invalid_citation_cases']}. Valid IDs do not establish claim support.\n")
    return '\n'.join(lines)


def render(results, reviews, summary):
    parts = ['# Emergency-answer quality evaluation\n', overview(summary)]
    for result in results:
        parts += [f"\n## {suite.key(result)} — {result['outcome']}\n", result['request']['q'],
                  '\n### Displayed answer\n', result['answer'] or '(No answer)',
                  '\n### Assessment\n', assessment_text(reviews.get(suite.key(result)))]
    return '\n'.join(parts)


def comparison(data):
    parts = ['# Paired emergency-answer comparison\n',
             f"Exact-request pairs: {data['matched']}. Request mismatches: {data['request_mismatches']}.",
             f"Only before: {data['only_before']}. Only after: {data['only_after']}.",
             'One stochastic sample does not establish a causal improvement. Historical cases are not a holdout.',
             '\n## Matched cases before\n', overview(data['paired_before_summary']),
             '\n## Matched cases after\n', overview(data['paired_after_summary']),
             '\n## Whole run before\n', overview(data['before_summary']),
             '\n## Whole run after\n', overview(data['after_summary'])]
    for pair in data['pairs']:
        parts += [f"\n## {pair['key']}\n", pair['after']['request']['q']]
        for side in ('before', 'after'):
            parts += [f'\n### {side.title()}\n', pair[side]['answer'],
                      assessment_text(pair[side + '_review'])]
    return '\n'.join(parts)
