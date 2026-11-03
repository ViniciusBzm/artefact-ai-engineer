"""Record checked conversations using the real LLM or the offline demonstration."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from emporio.agent import EmporioAgent
from emporio.evaluation import DEMO_TOKEN, check_reply
from emporio.security import Authenticator

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [
    ('01_catalog_under_budget', [
        ('Show acoustic guitars under R$ 1000', 'find_products', ['Violões', 'Yamaha C40']),
        ('And under R$ 500?', 'find_products', ['Violões', 'Tagima Memphis']),
    ]),
    ('02_product_and_nonstacking_discount', [
        ('What is the price of Crafter HT-100?', 'get_product', ['R$ 1.967,18', '18%']),
        ('And with PIX?', 'get_product', ['R$ 1.967,18', 'cannot be combined']),
    ]),
    ('03_order_privacy_multiturn', [
        ('What is the status of order 8?', 'order_status', ['/login']),
        ('order 8 customer002@example.test', 'order_status', ['/login']),
        ('/login', None, []),
        ('order 8', 'order_status', ['shipped', 'DEMO-TRACK-0008']),
        ('Show order 1', 'order_status', ["couldn't access"]),
    ]),
    ('04_online_returns_policy', [
        ('I regret my online purchase. Can I return it?', 'consult_policy', ['7 calendar days', 'p. 4']),
    ]),
    ('05_out_of_scope', [
        ("What's the weather on Mars?", 'out_of_scope', ['musical instruments']),
        ('Do you sell strings for acoustic guitars?', 'consult_policy', ['do not sell strings']),
    ]),
]


def generate_examples(*, use_llm=False, output_dir=None, receipt_path=None):
    if use_llm and not os.getenv('OPENAI_API_KEY', '').strip():
        raise ValueError('--llm requires OPENAI_API_KEY')
    output_dir = Path(output_dir or ROOT / ('examples' if use_llm else '.local/examples-offline'))
    receipt_path = Path(receipt_path or ROOT / '.local/examples-run.json')
    recorded = datetime.now(timezone.utc).isoformat()
    report = {'executed_at_utc': recorded, 'mode': 'real LLM + local tools' if use_llm else 'offline rules',
              'model': None, 'validated_provider_calls': 0, 'local_security_turns': 0,
              'conversations': []}
    documents = {}
    for title, messages in SCENARIOS:
        agent = EmporioAgent(ROOT / 'data/demo', use_llm=use_llm,
                             authenticator=Authenticator({hashlib.sha256(DEMO_TOKEN.encode()).hexdigest(): 2}))
        conversation = {'id': title, 'turns': []}
        try:
            if use_llm:
                report['model'] = agent.router.model
            local_only = title == '03_order_privacy_multiturn'
            if local_only:
                mode = 'Local order authorization and ownership checks'
            elif use_llm:
                mode = f'OpenAI Responses API, {agent.router.model}, with local tools'
            else:
                mode = 'Offline demonstration with local rules'
            lines = [f"# {title.replace('_', ' ').title()}", '', f'Execution: {mode}.',
                     f'Recorded at {recorded} (UTC).',
                     'Dataset: supplied catalog and synthetic customer/order records.', '']
            for message, route, contains in messages:
                if message == '/login':
                    if not agent.authenticate(DEMO_TOKEN):
                        raise RuntimeError('Synthetic fixture login failed')
                    lines += ['**Local sign-in:** Demo customer 2 authenticated through the local support-token mechanism.', '']
                    conversation['turns'].append({'event': 'local_login', 'synthetic_customer_id': 2})
                    continue
                reply = agent.reply(message)
                problems = check_reply(reply, {'route': route, 'contains': contains, 'excludes': []})
                evidence = agent.router.last_evidence
                local = 'local authorization' in reply.route or 'privacy_guard' in reply.route
                if use_llm and not local:
                    if not (evidence and evidence.get('validated') and evidence.get('response_id')):
                        problems.append('missing validated provider evidence')
                    else:
                        report['validated_provider_calls'] += 1
                if local:
                    report['local_security_turns'] += 1
                conversation['turns'].append({'message': message, 'response': reply.text,
                    'route': reply.route, 'source': reply.source, 'tool_call': evidence,
                    'local_security_path': local, 'passed': not problems, 'problems': problems})
                if problems:
                    report['conversations'].append(conversation)
                    receipt_path.parent.mkdir(parents=True, exist_ok=True)
                    receipt_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                    raise RuntimeError(f'{title}: conversation acceptance checks failed: {problems}')
                lines += [f'**Customer:** {message}', '', f'**Assistant:** {reply.text}', '',
                          f'*Tool path:* {reply.route}', '', f"*Source:* {reply.source or 'none'}", '', '---', '']
                print(f'{title}: {reply.route}', flush=True)
            report['conversations'].append(conversation)
            documents[title + '.md'] = '\n'.join(lines)
        finally:
            agent.close()
            if agent.router.client is not None:
                agent.router.client.close()
    # Publish the set only after every conversation and provider receipt passes.
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in documents.items():
        (output_dir / name).write_text(content, encoding='utf-8')
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llm', action='store_true', help='Record using OpenAI; makes seven billable requests')
    parser.add_argument('--output-dir', type=Path, help='Defaults to examples for --llm, otherwise .local/examples-offline')
    parser.add_argument('--receipt', type=Path, help='Execution receipt; defaults to ignored .local/examples-run.json')
    args = parser.parse_args()
    try:
        report = generate_examples(use_llm=args.llm, output_dir=args.output_dir, receipt_path=args.receipt)
    except (ValueError, RuntimeError) as error:
        parser.exit(2, f'Example generation failed: {error}\n')
    print(f"Recorded {len(report['conversations'])} conversations; {report['validated_provider_calls']} validated provider calls.")


if __name__ == '__main__':
    main()
