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


def expectations(case: dict) -> list[dict]:
    messages = case.get('messages')
    if not isinstance(messages, list) or not messages or any(not isinstance(m, str) or not m.strip() for m in messages):
        raise ValueError('Each scenario needs nonempty text messages')
    turns = case.get('turn_expectations', [case] if len(messages) == 1 else [])
    if len(turns) != len(messages):
        raise ValueError('Every conversation turn requires explicit acceptance criteria')
    if any(not isinstance(t.get('route'), str) or not isinstance(t.get('contains'), list)
           or not isinstance(t.get('excludes'), list) for t in turns):
        raise ValueError('Each turn needs route, contains and excludes criteria')
    return turns


def check_reply(reply, expected: dict) -> list[str]:
    problems = []
    if reply.route.split(' | ')[0] != expected['route']:
        problems.append('unexpected route')
    problems.extend(f'missing expected text: {text}' for text in expected['contains'] if text not in reply.text)
    problems.extend(f'forbidden text present: {text}' for text in expected['excludes'] if text in reply.text)
    if any(label in reply.route for label in ['llm_error', 'fallback', 'invalid_tool']):
        problems.append('provider/tool execution failure')
    return problems


def evaluate(*, use_llm=False, cases=None) -> dict:
    """Only synthetic/sanitized demo fixtures enter evaluation reports."""
    if use_llm and not os.environ.get('OPENAI_API_KEY'):
        raise ValueError('Live evaluation requires application OPENAI_API_KEY; no call was made')
    if cases is None:
        cases = json.loads((ROOT / 'eval/scenarios.json').read_text(encoding='utf-8'))
    if not cases or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Scenarios must have unique IDs and cannot be empty')
    for case in cases:
        expectations(case)
    results = []
    for case in cases:
        auth = Authenticator({hashlib.sha256(DEMO_TOKEN.encode()).hexdigest(): 2})
        a = EmporioAgent(ROOT / 'data/demo', use_llm=use_llm, authenticator=auth)
        started = time.perf_counter()
        try:
            if case.get('login'):
                assert a.authenticate(DEMO_TOKEN)
            turns, problems = [], []
            for index, (message, expected) in enumerate(zip(case['messages'], expectations(case)), 1):
                reply = a.reply(message)
                turn_problems = check_reply(reply, expected)
                evidence = a.router.last_evidence
                local = 'NO LLM' in reply.route and ('local authorization' in reply.route or 'privacy_guard' in reply.route)
                if use_llm and not local and not (evidence and evidence.get('validated') and evidence.get('response_id')):
                    turn_problems.append('missing validated real-provider response evidence')
                problems.extend(f'turn {index}: {p}' for p in turn_problems)
                turns.append({'turn': index, 'passed': not turn_problems, 'route': reply.route,
                              'source': reply.source, 'problems': turn_problems,
                              'tool_call': evidence, 'local_security_path': local})
                if use_llm and any(label in reply.route for label in ['llm_error', 'fallback', 'invalid_tool']):
                    break
            results.append({'id': case['id'], 'passed': not problems, 'problems': problems,
                            'route': reply.route, 'source': reply.source,
                            'turns': turns,
                            'elapsed_seconds': round(time.perf_counter() - started, 4)})
        finally:
            a.close()
            if a.router.client is not None:
                a.router.client.close()
        if use_llm and any(any(label in t['route'] for label in ['llm_error', 'fallback', 'invalid_tool']) for t in turns):
            break
    return {'executed_at_utc': datetime.now(timezone.utc).isoformat(),
            'mode': 'real LLM + local tools' if use_llm else 'offline rules (NO LLM)',
            'model': a.router.model if use_llm else None,
            'cases': len(results), 'passed': sum(r['passed'] for r in results),
            'requested_cases': len(cases), 'stopped_early': len(results) < len(cases) or any(len(r['turns']) < len(case['messages']) for r, case in zip(results, cases)),
            'failed': sum(not r['passed'] for r in results), 'results': results,
            'turns': sum(len(r['turns']) for r in results),
            'validated_provider_calls': sum(bool(t['tool_call'] and t['tool_call'].get('validated')) for r in results for t in r['turns']),
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
