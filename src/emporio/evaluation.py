"""Scenario evaluation with factual, route and privacy assertions; no LLM judge."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from .agent import EmporioAgent
from .security import Authenticator

ROOT = Path(__file__).resolve().parents[2]
DEMO_TOKEN = 'synthetic-test-token-customer-2-only'


def evaluate(*, use_llm=False, cases=None) -> dict:
    """Only synthetic/sanitized demo fixtures enter evaluation reports."""
    if use_llm and not os.environ.get('OPENAI_API_KEY'):
        raise ValueError('Live evaluation requires application OPENAI_API_KEY; no call was made')
    if cases is None:
        cases = json.loads((ROOT / 'eval/scenarios.json').read_text(encoding='utf-8'))
    results = []
    for case in cases:
        auth = Authenticator({hashlib.sha256(DEMO_TOKEN.encode()).hexdigest(): 2})
        a = EmporioAgent(ROOT / 'data/demo', use_llm=use_llm, authenticator=auth)
        started = time.perf_counter()
        try:
            if case.get('login'):
                assert a.authenticate(DEMO_TOKEN)
            replies = [a.reply(message) for message in case['messages']]
            reply = replies[-1]
            problems = []
            if reply.route.split(' | ')[0] != case['route']:
                problems.append('unexpected route')
            problems.extend(f'missing expected text: {text}' for text in case['contains'] if text not in reply.text)
            problems.extend(f'forbidden text present: {text}' for text in case['excludes'] if text in reply.text)
            if any('llm_error' in r.route or 'fallback' in r.route or 'invalid_tool' in r.route for r in replies):
                problems.append('provider/tool execution failure; not a successful LLM result')
            results.append({'id': case['id'], 'passed': not problems, 'problems': problems,
                            'route': reply.route, 'source': reply.source,
                            'elapsed_seconds': round(time.perf_counter() - started, 4)})
        finally:
            a.close()
            if a.router.client is not None:
                a.router.client.close()
    return {'executed_at_utc': datetime.now(timezone.utc).isoformat(),
            'mode': 'real LLM + local tools' if use_llm else 'offline rules (NO LLM)',
            'model': a.router.model if use_llm else None,
            'cases': len(results), 'passed': sum(r['passed'] for r in results),
            'failed': sum(not r['passed'] for r in results), 'results': results,
            'scope': 'Fixed demo regression scenarios; not a production accuracy estimate'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llm', action='store_true', help='Make real, billable API calls; requires OPENAI_API_KEY')
    parser.add_argument('--output', type=Path, default=ROOT / '.local/evaluation.json')
    args = parser.parse_args()
    try:
        report = evaluate(use_llm=args.llm)
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{report['passed']}/{report['cases']} passed; {report['mode']}; report: {args.output}")
    raise SystemExit(1 if report['failed'] else 0)


if __name__ == '__main__':
    main()
