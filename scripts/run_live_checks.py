"""Safe local preflight and opt-in real-provider verification. Never prints keys."""
import argparse
import importlib.util
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'gpt-5.4-mini-2026-03-17'


def prepare_environment(key_file: Path | None = None, interval_seconds: float = 7.0) -> tuple[dict, dict]:
    if not math.isfinite(interval_seconds) or not 0 <= interval_seconds <= 60:
        raise ValueError('Request interval must be finite and between 0 and 60 seconds')
    env = dict(os.environ)
    private = ROOT / '.local'
    path = (key_file or private / 'openai_api_key.txt').resolve()
    try:
        path.relative_to(private.resolve())
    except ValueError:
        raise ValueError('Key files must stay inside the ignored project .local directory') from None
    origin = 'process environment' if env.get('OPENAI_API_KEY', '').strip() else 'missing'
    if origin == 'missing' and path.is_file():
        value = path.read_text(encoding='utf-8-sig').strip()
        if value:
            env['OPENAI_API_KEY'] = value
            origin = 'ignored local key file'
    key = env.get('OPENAI_API_KEY', '').strip()
    recognized = bool(re.fullmatch(r'sk-[A-Za-z0-9_-]{30,}', key))
    env['OPENAI_API_KEY'] = key
    env['OPENAI_MODEL'] = env.get('OPENAI_MODEL') or MODEL
    env['RUN_LIVE_LLM'] = '1'
    env['PYTHONUTF8'] = '1'
    env['EMPORIO_MIN_REQUEST_INTERVAL_SECONDS'] = str(interval_seconds)
    env.pop('OPENAI_LOG', None)
    missing = [p for p in ['openai', 'pytest', 'httpx'] if not importlib.util.find_spec(p)]
    report = {'provider': 'OpenAI Responses API', 'model': env['OPENAI_MODEL'],
              'credential_present': bool(key), 'credential_source': origin,
              'credential_format_recognized': recognized,
              'missing_dependencies': missing, 'ready_to_attempt': recognized and not missing,
              'real_api_executed': False,
              'minimum_request_interval_seconds': interval_seconds,
              'rate_note': 'Sequential process pacing only; remaining daily quota, shared traffic and token limits are not known.',
              'note': 'Preflight does not establish key validity, billing or model access.'}
    return env, report


def smoke_check(env: dict, private: Path) -> dict:
    """Exactly one model request at most; SDK retries remain disabled."""
    from openai import OpenAI
    from emporio.agent import EmporioAgent
    client = OpenAI(api_key=env['OPENAI_API_KEY'], base_url='https://api.openai.com/v1',
                    timeout=20.0, max_retries=0)
    agent = EmporioAgent(ROOT / 'data/demo', use_llm=True)
    agent.router.model = env['OPENAI_MODEL']
    agent.router.client = client
    try:
        reply = agent.reply('What is the price of the Takamine GD20?')
        result = {'planned_max_requests': 1, 'automatic_retries': 0,
                  'passed': reply.route.startswith('get_product | LLM tool call') and 'R$ 2.199,00' in reply.text,
                  'route': reply.route, 'evidence': agent.router.last_evidence,
                  'note': 'A successful smoke check is not full integration/evaluation validation.'}
        (private / 'smoke-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        return result
    finally:
        agent.close()
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file', type=Path, help='Optional key file under project .local; environment takes precedence')
    parser.add_argument('--run', action='store_true', help='Make at most one billable smoke-test request, without retries')
    parser.add_argument('--full-suite', action='store_true', help='Explicit additional opt-in: run full integration/evaluation after reviewing quota and cost')
    parser.add_argument('--interval-seconds', type=float, default=7.0,
                        help='Minimum spacing between provider requests (default 7s)')
    args = parser.parse_args()
    if args.full_suite and not args.run:
        parser.error('--full-suite requires --run and explicit operator review of cost/quota')
    try:
        env, report = prepare_environment(args.key_file, args.interval_seconds)
    except (ValueError, OSError) as error:
        parser.error(str(error) if isinstance(error, ValueError) else 'Unable to read private credential file')
    private = ROOT / '.local'
    private.mkdir(exist_ok=True)
    (private / 'live_preflight.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if not args.run:
        return
    if not report['ready_to_attempt']:
        parser.error('Live checks blocked: a recognizable application secret key and .[all] dependencies are required. No API call was made.')
    from emporio.budget import initialize, summary, MODEL as PRICED_MODEL
    if env.get('OPENAI_MODEL', MODEL) != PRICED_MODEL:
        parser.error('USD 1 guard requires the pinned, explicitly priced model')
    budget_path = private / 'live-budget-usd1.json'
    initialize(budget_path)
    env['EMPORIO_LIVE_BUDGET_FILE'] = str(budget_path)
    print(json.dumps({'budget_before': summary(budget_path)}, indent=2))
    if not args.full_suite:
        names = ['EMPORIO_LIVE_BUDGET_FILE', 'EMPORIO_MIN_REQUEST_INTERVAL_SECONDS']
        previous = {name: os.environ.get(name) for name in names}
        try:
            for name in names:
                os.environ[name] = env[name]
            result = smoke_check(env, private)
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        print(json.dumps(result, indent=2))
        print(json.dumps({'budget_after': summary(budget_path)}, indent=2))
        raise SystemExit(0 if result['passed'] else 1)
    xml = private / 'live-tests.xml'
    process = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x', '-m', 'live',
                              f'--junitxml={xml}'], cwd=ROOT, env=env)
    if process.returncode:
        raise SystemExit(process.returncode)
    cases = ET.parse(xml).getroot().findall('.//testcase')
    if not cases or any(c.find('skipped') is not None for c in cases):
        parser.error('Live verification did not execute every selected test; no success claim is valid')
    # The SDK pacer is process-local; keep the transition to the evaluation
    # subprocess from starting immediately after the last integration request.
    time.sleep(args.interval_seconds)
    raise SystemExit(subprocess.run([sys.executable, '-m', 'emporio.evaluation', '--llm',
                                    '--output', str(private / 'evaluation_llm.json')], cwd=ROOT, env=env).returncode)


if __name__ == '__main__':
    main()
