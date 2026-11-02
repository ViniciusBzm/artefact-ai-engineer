from pathlib import Path
from decimal import Decimal
import pytest
import hashlib
from emporio.security import Authenticator

from emporio.agent import EmporioAgent
from emporio.store import Store, brl, discounted
from emporio.router import budget

DATA = Path(__file__).resolve().parents[1] / 'data' / 'demo'


@pytest.fixture
def agent():
    item = EmporioAgent(DATA, authenticator=Authenticator({hashlib.sha256(b'synthetic-test-token-customer-2-only').hexdigest(): 2}))
    yield item
    item.close()


def test_data_integrity():
    s = Store(DATA)
    assert s.db.execute('select count(*) from products').fetchone()[0] == 65
    assert s.db.execute('select count(*) from customers').fetchone()[0] == 2
    assert s.db.execute('select count(*) from orders').fetchone()[0] == 2
    assert s.db.execute('select count(*) from promotions where is_active=1').fetchone()[0] == 4


def test_catalog_budget_returns_available_violoes_only(agent):
    reply = agent.reply('Quais opções de violões disponíveis custando até R$1000?')
    assert 'Yamaha C40' in reply.text
    assert 'R$ 599,90' in reply.text
    assert 'Takamine GD20' not in reply.text
    assert 'Violões' in reply.text


def test_exact_price_is_from_data(agent):
    reply = agent.reply('Quanto custa o Takamine GD20?')
    assert 'Takamine GD20' in reply.text
    assert 'R$ 2.199,00' in reply.text
    assert '5 in stock' in reply.text
    assert 'promotion' not in reply.text


def test_pix_discount_and_promotion_are_non_cumulative(agent):
    p = agent._product('Crafter HT-100 no PIX')
    assert '18% active promotion' in p.text
    assert 'cannot be combined' in p.text
    assert 'R$ 1.967,18' in p.text
    normal = agent._product('Takamine GD20 no PIX')
    assert 'R$ 2.089,05' in normal.text


def test_no_expired_promotion(agent):
    answer = agent.reply('Quanto custa o Takamine GD20?').text
    assert '12%' not in answer  # corresponding promotional row is inactive


def test_request_order_requires_authenticated_session(agent):
    r = agent.reply('Qual o status do pedido 8?')
    assert '/login' in r.text
    assert 'shipped' not in r.text
    wrong = agent.reply('outsider@example.test')
    assert 'remove personal' in wrong.text
    assert 'shipped' not in wrong.text


def test_authenticated_principal_unlocks_exact_order(agent):
    first = agent.reply('What is the status of order 8?')
    assert '/login' in first.text
    assert agent.authenticate('synthetic-test-token-customer-2-only')
    second = agent.reply('order 8')
    assert 'shipped' in second.text
    assert 'DEMO-TRACK-0008' in second.text


def test_order_exists_but_wrong_email_same_failure_as_nonexistent(agent):
    a = agent.reply('order 8 customer001@example.test')
    b = agent.reply('order 987 customer001@example.test')
    assert a.text == b.text


def test_returns_cite_manual_and_ask_followup(agent):
    answer = agent.reply('Me arrependi da minha compra online, posso devolver?').text
    assert '7 calendar days' in answer
    assert '[Store manual, p. 4]' in answer
    assert 'date did you receive' in answer


def test_store_hours(agent):
    assert 'Saturday' in agent.reply('Qual é o horário de funcionamento?').text


def test_unsupported_question(agent):
    text = agent.reply('Qual a previsão do tempo na Lua?').text
    assert 'musical instruments' in text


def test_followup_budget_keeps_category(agent):
    agent.reply('Quais violões vocês têm disponíveis?')
    result = agent.reply('E até R$ 500?')
    assert 'Violões' in result.text
    assert 'Yamaha C40' not in result.text
    assert 'Tagima Memphis' in result.text


def test_no_cost_leak_in_wrong_order(agent):
    message = agent.reply('pedido 1 wrong@example.test').text
    assert 'R$' not in message
    assert 'Tracking' not in message


def test_currency_and_promo_calculation():
    assert brl('2399') == 'R$ 2.399,00'
    assert discounted('2399', 18) == Decimal('1967.18')
    assert budget('Até R$ 1.000') == 1000
    assert budget('under 1000') == 1000


def test_accessory_request_does_not_turn_into_guitar_recommendation(agent):
    result = agent.reply('Vocês vendem cordas de guitarra?')
    assert 'do not sell strings' in result.text
    assert 'Fender Telecaster' not in result.text


def test_specific_model_stock_question(agent):
    result = agent.reply('Qual a disponibilidade do Fender Telecaster?')
    assert 'Fender Telecaster Player Series' in result.text
    assert '15 in stock' in result.text
