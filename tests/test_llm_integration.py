"""Real SDK + mocked HTTP transport; a separate opt-in test calls the real API."""
import json
import os
import hashlib
from pathlib import Path

import httpx
import pytest

from emporio.agent import EmporioAgent
from emporio.router import ProviderError, Router, TOOL_SPEC, validate_call
from emporio.security import Authenticator

DATA = Path(__file__).resolve().parents[1] / 'data/demo'


def response_body(name='get_product', arguments=None, *, calls=1, status='completed'):
    args = {'query': 'Takamine GD20'} if arguments is None else arguments
    return {'id': 'resp_test', 'object': 'response', 'created_at': 1, 'status': status,
            'model': 'test-model', 'output': [
                {'type': 'function_call', 'id': f'fc_{i}', 'call_id': f'call_{i}',
                 'name': name, 'arguments': json.dumps(args), 'status': 'completed'} for i in range(calls)]}


def sdk_client(handler):
    from openai import OpenAI
    return OpenAI(api_key='dummy-offline-test-key', max_retries=0,
                  http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_real_sdk_serializes_strict_private_nonpersistent_payload_and_dispatches():
    captured = []
    def handler(request):
        captured.append(json.loads(request.content))
        assert request.url.path == '/v1/responses'
        return httpx.Response(200, json=response_body())
    agent = EmporioAgent(DATA, use_llm=True)
    client = sdk_client(handler)
    agent.router.client = client
    try:
        result = agent.reply('What is the price of Takamine GD20?')
        assert 'LLM tool call' in result.route and 'R$ 2.199,00' in result.text
        payload = captured[0]
        assert payload['store'] is False and payload['parallel_tool_calls'] is False
        assert payload['tool_choice'] == 'required'
        assert payload['max_output_tokens'] == 1200
        for spec in payload['tools']:
            assert spec['strict'] is True
            assert spec['parameters']['additionalProperties'] is False
            assert set(spec['parameters']['required']) == set(spec['parameters']['properties'])
        prompt = json.dumps(payload)
        assert 'customer002@example.test' not in prompt and 'DEMO-TRACK' not in prompt
        assert not any(x in prompt for x in ['SELECT ', 'total_brl', 'tracking_code'])
    finally:
        agent.close()
        client.close()


@pytest.mark.parametrize('body', [
    response_body(calls=0), response_body(calls=2), response_body(status='incomplete'),
    response_body('execute_sql', {'sql': 'SELECT * FROM customers'}),
    response_body('order_status', {'customer_id': 2}),
    response_body('find_products', {'category': 'Violões', 'keywords': '', 'max_price': '1000'}),
    response_body('consult_policy', {'topic': 'invented'}),
])
def test_malformed_provider_output_never_executes_tools(body):
    client = sdk_client(lambda req: httpx.Response(200, json=body))
    try:
        with pytest.raises(ProviderError):
            Router(use_llm=True, client=client).route('hello', [])
    finally:
        client.close()


@pytest.mark.parametrize('code', [401, 429, 500])
def test_provider_failures_are_visible_and_sanitized(code):
    client = sdk_client(lambda req: httpx.Response(code, json={'error': {'message': 'SECRET PRIVATE BODY'}}))
    try:
        with pytest.raises(ProviderError) as exc:
            Router(use_llm=True, client=client).route('hello', [])
        assert 'SECRET' not in str(exc.value)
        router = Router(use_llm=True, client=client, allow_fallback=True)
        name, args, mode = router.route('hello', [])
        assert name == 'greeting' and 'offline fallback (NO LLM' in mode
    finally:
        client.close()


def test_timeout_fails_without_retry_or_private_error_body():
    count = 0
    def timeout(request):
        nonlocal count
        count += 1
        raise httpx.ReadTimeout('PRIVATE BODY', request=request)
    client = sdk_client(timeout)
    try:
        with pytest.raises(ProviderError, match='APITimeoutError'):
            Router(use_llm=True, client=client).route('hello', [])
        assert count == 1
    finally:
        client.close()


@pytest.mark.parametrize('price', [float('nan'), float('inf'), -1, 0, True, '1000', 1_000_001])
def test_numeric_arguments_do_not_accept_nonfinite_or_coerced_values(price):
    with pytest.raises(ValueError):
        validate_call('find_products', {'category': '', 'keywords': '', 'max_price': price})


@pytest.mark.live
@pytest.mark.skipif(not (os.getenv('RUN_LIVE_LLM') == '1' and os.getenv('OPENAI_API_KEY')),
                    reason='Real API test requires RUN_LIVE_LLM=1 and application OPENAI_API_KEY')
def test_real_provider_selects_and_executes_grounded_product_tool():
    a = EmporioAgent(DATA, use_llm=True)
    try:
        result = a.reply('What is the price of the Takamine GD20?')
        assert result.route.startswith('get_product | LLM tool call')
        assert 'R$ 2.199,00' in result.text
        assert 'fallback' not in result.route
    finally:
        a.close()
        if a.router.client is not None:
            a.router.client.close()


@pytest.mark.live
@pytest.mark.skipif(not (os.getenv('RUN_LIVE_LLM') == '1' and os.getenv('OPENAI_API_KEY')),
                    reason='Real API test requires RUN_LIVE_LLM=1 and application OPENAI_API_KEY')
@pytest.mark.parametrize('conversation', [
    [('What is the price of Takamine GD20?', 'get_product', 'R$ 2.199,00'),
     ('And with PIX?', 'get_product', 'R$ 2.089,05')],
    [('Show acoustic guitars', 'find_products', 'Violões'),
     ('And under R$ 500?', 'find_products', 'Tagima Memphis')],
    [('Can I return an online purchase?', 'consult_policy', '7 calendar days'),
     ('What are your opening hours?', 'consult_policy', 'Saturday')],
])
def test_real_provider_multiturn_tool_execution(conversation):
    a = EmporioAgent(DATA, use_llm=True)
    try:
        for message, tool, expected in conversation:
            reply = a.reply(message)
            assert reply.route.startswith(f'{tool} | LLM tool call')
            assert expected in reply.text
            assert a.router.last_evidence['validated']
            assert a.router.last_evidence['response_id']
    finally:
        a.close()
        if a.router.client is not None:
            a.router.client.close()


@pytest.mark.live
@pytest.mark.skipif(not (os.getenv('RUN_LIVE_LLM') == '1' and os.getenv('OPENAI_API_KEY')),
                    reason='Real API test requires RUN_LIVE_LLM=1 and application OPENAI_API_KEY')
def test_real_provider_session_preserves_local_order_boundary():
    token = 'synthetic-test-token-customer-2-only'
    a = EmporioAgent(DATA, use_llm=True,
                     authenticator=Authenticator({hashlib.sha256(token.encode()).hexdigest(): 2}))
    try:
        assert a.authenticate(token)
        reply = a.reply('What is the price of Takamine GD20?')
        assert 'LLM tool call' in reply.route and a.router.last_evidence['validated']
        assert 'shipped' in a.reply('order 8').text
        assert a.router.last_evidence is None
        assert "couldn't access" in a.reply('order 1').text
        assert a.router.last_evidence is None
        reply = a.reply('And with PIX?')
        assert 'R$ 2.089,05' in reply.text and a.router.last_evidence['validated']
    finally:
        a.close()
        if a.router.client is not None:
            a.router.client.close()
