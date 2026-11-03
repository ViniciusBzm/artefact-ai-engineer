"""Conservative local spend guard for sequential live verification, not billing.

Reserve the model's ENTIRE 400k input context and maximum requested output before
each request. Reconcile reported usage with a 25% pricing margin. Missing usage or
transport failures retain the full reservation. No credentials/prompts are stored.
"""
from contextlib import contextmanager
from decimal import Decimal
import json
import os
from pathlib import Path

MODEL = 'gpt-5.4-mini-2026-03-17'
INPUT_RATE = Decimal('0.75') / 1_000_000
OUTPUT_RATE = Decimal('4.50') / 1_000_000
MARGIN = Decimal('1.25')
RESERVATION = (400_000 * INPUT_RATE + 1200 * OUTPUT_RATE) * MARGIN


class BudgetExceeded(RuntimeError):
    pass


@contextmanager
def ledger(path: Path):
    lock = path.with_suffix('.lock')
    # Fail closed on competing processes or a stale lock after a crash.
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        yield value
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        os.replace(temporary, path)
    finally:
        os.close(descriptor)
        lock.unlink()


def initialize(path: Path):
    """One persistent USD 1 allowance; repeated runner invocations never reset it."""
    path.parent.mkdir(exist_ok=True)
    try:
        with path.open('x', encoding='utf-8') as file:
            json.dump({'limit_usd': '1.00', 'model': MODEL, 'requests': [],
                       'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-5.4-mini',
                       'pricing_checked': '2026-11-02', 'pricing_margin': str(MARGIN)}, file, indent=2)
    except FileExistsError:
        pass
    with ledger(path) as value:
        if value['limit_usd'] != '1.00' or value['model'] != MODEL:
            raise BudgetExceeded('Unexpected existing budget configuration')


def reserve(path: Path, model: str) -> int:
    if model != MODEL:
        raise BudgetExceeded('Budget guard only supports the priced pinned model')
    with ledger(path) as value:
        requests = value['requests']
        charged = sum((Decimal(r['budget_charge_usd']) for r in requests), Decimal(0))
        if value['limit_usd'] != '1.00' or len(requests) >= 80 or charged + RESERVATION > Decimal('1.00'):
            raise BudgetExceeded('Live verification budget exhausted; no API request sent')
        requests.append({'state': 'reserved', 'budget_charge_usd': str(RESERVATION)})
        return len(requests) - 1


def settle(path: Path, ticket: int, response):
    usage = getattr(response, 'usage', None)
    inputs = getattr(usage, 'input_tokens', None)
    outputs = getattr(usage, 'output_tokens', None)
    if (getattr(response, 'model', None) != MODEL or type(inputs) is not int or
            type(outputs) is not int or not 0 <= inputs <= 400_000 or not 0 <= outputs <= 1200):
        raise BudgetExceeded('Unexpected usage/model; full reservation retained, stop verification')
    estimate = inputs * INPUT_RATE + outputs * OUTPUT_RATE
    with ledger(path) as value:
        record = value['requests'][ticket]
        if record['state'] != 'reserved':
            raise BudgetExceeded('Usage was already reconciled')
        record.update(state='reported_usage', input_tokens=inputs, output_tokens=outputs,
                      response_id=response.id, estimated_cost_usd=str(estimate),
                      budget_charge_usd=str(estimate * MARGIN))


def summary(path: Path) -> dict:
    with ledger(path) as value:
        requests = value['requests']
        return {'limit_usd': value['limit_usd'], 'attempted_requests': len(requests),
                'usage_receipts': sum(r['state'] == 'reported_usage' for r in requests),
                'budget_charge_usd': str(sum((Decimal(r['budget_charge_usd']) for r in requests), Decimal(0))),
                'estimated_reported_usage_cost_usd': str(sum((Decimal(r.get('estimated_cost_usd', '0')) for r in requests), Decimal(0))),
                'note': 'Token-price estimate, not a billing receipt. Uncertain attempts retain full-context reservations. Scope: requests through this runner only.'}
