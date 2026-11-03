import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from emporio.agent import EmporioAgent
from emporio.evaluation import evaluate
from emporio.router import Router
from emporio.audit import audit
from test_llm_integration import sdk_client, response_body
import httpx

ROOT = Path(__file__).resolve().parents[1]


def test_contact_free_data_audit_is_reproducible():
    report = audit(ROOT / 'data/demo')
    assert report['tables']['products']['rows'] == 65
    assert report['tables']['customers']['rows'] == 2
    assert report['active_promotions'] == 4
    encoded = json.dumps(report)
    assert 'customer002@example.test' not in encoded and 'Demo Customer' not in encoded


def test_llm_route_does_not_call_deterministic_classifier(monkeypatch):
    monkeypatch.setattr('emporio.router.classify', Mock(side_effect=AssertionError('Rules must not interpret this message')))
    client = sdk_client(lambda request: httpx.Response(200, json=response_body()))
    try:
        router = Router(use_llm=True, client=client)
        assert router.route('What is the price of Takamine GD20?', [])[0] == 'get_product'
        assert router.last_evidence['validated'] is True
        assert router.last_evidence['response_id'] == 'resp_test'
    finally:
        client.close()


def test_sdk_multiturn_uses_context_and_executes_two_tool_calls():
    payloads = []
    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=response_body())
    client = sdk_client(handler)
    a = EmporioAgent(ROOT / 'data/demo', use_llm=True)
    a.router.client = client
    try:
        assert 'R$ 2.199,00' in a.reply('What is the price of Takamine GD20?').text
        assert 'R$ 2.089,05' in a.reply('And with PIX?').text
        context = json.loads(payloads[1]['input'][0]['content'])
        assert context['previous_product'].startswith('Takamine GD20')
        assert context['recent_tool_context'][0][0] == 'get_product'
        assert len(payloads) == 2
        a.reply('order 8')
        assert a.router.last_evidence is None
        assert len(payloads) == 2
    finally:
        a.close()
        client.close()


def test_evaluation_rejects_unchecked_intermediate_turn():
    case = {'id': 'unchecked', 'messages': ['hello', 'hello'], 'route': 'greeting',
            'contains': [], 'excludes': []}
    with pytest.raises(ValueError, match='Every conversation turn'):
        evaluate(cases=[case])


def test_evaluation_records_intermediate_failure_even_if_last_turn_passes():
    case = {'id': 'false-positive', 'messages': ['Hello', 'Hello'], 'route': 'greeting', 'contains': [], 'excludes': [],
            'turn_expectations': [{'route': 'greeting', 'contains': ['deliberately absent'], 'excludes': []},
                                  {'route': 'greeting', 'contains': ['Empório'], 'excludes': []}]}
    report = evaluate(cases=[case])
    assert report['failed'] == 1
    assert not report['results'][0]['turns'][0]['passed']
    assert report['results'][0]['turns'][1]['passed']


@pytest.mark.parametrize('cases', [[], [{'id': 'x'}, {'id': 'x'}]])
def test_evaluation_rejects_empty_or_duplicate_cases(cases):
    with pytest.raises(ValueError):
        evaluate(cases=cases)


def load_runner():
    spec = importlib.util.spec_from_file_location('live_runner', ROOT / 'scripts/run_live_checks.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_preflight_reports_missing_key_without_api_call(monkeypatch, tmp_path):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    runner = load_runner()
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    _, report = runner.prepare_environment()
    assert not report['ready_to_attempt'] and not report['real_api_executed']
    assert report['minimum_request_interval_seconds'] == 7.0


def test_live_preflight_never_serializes_key(monkeypatch, tmp_path):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    runner = load_runner()
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    private = tmp_path / '.local'
    private.mkdir()
    token = 'sk-' + 'x' * 40  # Synthetic format fixture; never sent to a real provider.
    (private / 'openai_api_key.txt').write_text(token)
    env, report = runner.prepare_environment()
    assert env['OPENAI_API_KEY'] == token
    assert env['EMPORIO_MIN_REQUEST_INTERVAL_SECONDS'] == '7.0'
    assert token not in json.dumps(report)
    assert not report['real_api_executed']
    assert report['credential_format_recognized'] is True
    with pytest.raises(ValueError, match='inside'):
        runner.prepare_environment(tmp_path / 'external-key.txt')


def test_unrecognized_local_credential_is_blocked_without_network(monkeypatch, tmp_path):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    runner = load_runner()
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    private = tmp_path / '.local'
    private.mkdir()
    (private / 'openai_api_key.txt').write_text('not-a-real-openai-key-value')
    _, report = runner.prepare_environment()
    assert report['credential_present'] and not report['credential_format_recognized']
    assert not report['ready_to_attempt']


def test_run_defaults_to_one_smoke_check_and_never_starts_suite(monkeypatch, tmp_path):
    import sys
    runner = load_runner()
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'prepare_environment', lambda *args: (
        {'EMPORIO_MIN_REQUEST_INTERVAL_SECONDS': '0'}, {'ready_to_attempt': True}))
    smoke = Mock(return_value={'passed': True})
    monkeypatch.setattr(runner, 'smoke_check', smoke)
    launch = Mock(side_effect=AssertionError('Full suite must not start by default'))
    monkeypatch.setattr(runner.subprocess, 'run', launch)
    monkeypatch.setattr(sys, 'argv', ['run_live_checks.py', '--run'])
    with pytest.raises(SystemExit) as result:
        runner.main()
    assert result.value.code == 0
    smoke.assert_called_once()
    launch.assert_not_called()


def test_real_evaluation_stops_after_first_provider_error(monkeypatch):
    import emporio.evaluation as module
    from emporio.agent import Reply
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-not-used-by-a-provider')
    call = Mock(return_value=Reply('Authentication failed', 'llm_error (NO tool executed)', ''))
    monkeypatch.setattr(module.EmporioAgent, 'reply', call)
    cases = [{'id': str(i), 'messages': ['hello'], 'route': 'greeting', 'contains': [], 'excludes': []} for i in range(3)]
    report = module.evaluate(use_llm=True, cases=cases)
    assert call.call_count == 1
    assert report['stopped_early'] and report['cases'] == 1 and report['requested_cases'] == 3
