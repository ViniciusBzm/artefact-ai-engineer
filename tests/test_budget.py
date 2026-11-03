from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from emporio.budget import MODEL, RESERVATION, BudgetExceeded, initialize, reserve, settle, summary
from emporio.router import Router, ProviderError


def receipt(inputs=1000, outputs=10):
    return SimpleNamespace(model=MODEL, id='resp_synthetic',
                           usage=SimpleNamespace(input_tokens=inputs, output_tokens=outputs))


def test_uncertain_attempts_keep_full_reservations_and_block_third_request(tmp_path):
    path = tmp_path / 'budget.json'
    initialize(path)
    reserve(path, MODEL)
    initialize(path)  # A second invocation cannot silently reset the allowance.
    reserve(path, MODEL)
    with pytest.raises(BudgetExceeded):
        reserve(path, MODEL)
    assert summary(path)['attempted_requests'] == 2
    assert Decimal(summary(path)['budget_charge_usd']) == 2 * RESERVATION < 1


def test_reported_usage_is_reconciled_with_margin_and_never_charged_twice(tmp_path):
    path = tmp_path / 'budget.json'
    initialize(path)
    ticket = reserve(path, MODEL)
    settle(path, ticket, receipt())
    with pytest.raises(BudgetExceeded):
        settle(path, ticket, receipt())
    result = summary(path)
    assert Decimal(result['estimated_reported_usage_cost_usd']) == Decimal('0.0007950')
    assert Decimal(result['budget_charge_usd']) == Decimal('0.00099375')
    assert result['usage_receipts'] == 1


@pytest.mark.parametrize('inputs,outputs', [(None, 10), (-1, 10), (400001, 10), (100, 1201), (True, 10)])
def test_invalid_usage_retains_reservation(tmp_path, inputs, outputs):
    path = tmp_path / 'budget.json'
    initialize(path)
    ticket = reserve(path, MODEL)
    with pytest.raises(BudgetExceeded):
        settle(path, ticket, receipt(inputs, outputs))
    assert Decimal(summary(path)['budget_charge_usd']) == RESERVATION


def test_unpriced_model_and_competing_writer_fail_closed(tmp_path):
    path = tmp_path / 'budget.json'
    initialize(path)
    with pytest.raises(BudgetExceeded):
        reserve(path, 'unpriced-model')
    path.with_suffix('.lock').touch()
    with pytest.raises(FileExistsError):
        reserve(path, MODEL)


def test_router_blocks_transport_when_allowance_is_insufficient(monkeypatch, tmp_path):
    path = tmp_path / 'budget.json'
    initialize(path)
    reserve(path, MODEL)
    reserve(path, MODEL)
    monkeypatch.setenv('EMPORIO_LIVE_BUDGET_FILE', str(path))
    monkeypatch.setenv('EMPORIO_MIN_REQUEST_INTERVAL_SECONDS', '0')
    client = Mock()
    router = Router(use_llm=True, model=MODEL, client=client)
    with pytest.raises(ProviderError, match='BudgetExceeded'):
        router.route('Hello', [])
    client.responses.create.assert_not_called()
    assert router.last_evidence is None


def test_request_count_ceiling_persists_even_for_zero_usage(tmp_path):
    path = tmp_path / 'budget.json'
    initialize(path)
    for _ in range(80):
        settle(path, reserve(path, MODEL), receipt(0, 0))
    with pytest.raises(BudgetExceeded):
        reserve(path, MODEL)
