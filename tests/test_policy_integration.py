import hashlib
import os
from pathlib import Path
import shutil

import pytest

from emporio.agent import EmporioAgent
from emporio.policy import PolicyBook, POLICIES
from emporio.security import Authenticator

DATA = Path(__file__).resolve().parents[1] / 'data/demo'


@pytest.mark.parametrize('topic', list(POLICIES))
def test_every_demo_policy_has_loaded_evidence_and_citation(topic):
    book = PolicyBook(DATA)
    passages = book.retrieve(topic)
    text, source = book.lookup(topic)
    assert passages and all(p.text and p.digest == book.digest for p in passages)
    assert 'Store manual' in text and 'sha256' in source


def test_modified_policy_with_same_heading_is_rejected(tmp_path):
    shutil.copytree(DATA, tmp_path / 'data')
    file = tmp_path / 'data/policies_demo.json'
    file.write_text(file.read_text(encoding='utf-8').replace('seven', 'seventy'), encoding='utf-8')
    with pytest.raises(ValueError, match='Unreviewed'):
        PolicyBook(file.parent)


def test_ambiguous_rules_are_not_silently_resolved():
    b = PolicyBook(DATA)
    assert 'exactly R$ 500 is unspecified' in b.lookup('shipping')[0]
    assert 'ambiguous' in b.lookup('installments')[0]
    assert 'both' in b.lookup('contact')[0]


SOURCE = os.environ.get('EMPORIO_SOURCE_DIR')


@pytest.mark.skipif(not SOURCE, reason='Set EMPORIO_SOURCE_DIR to private original six CSVs and policy PDF')
def test_original_sources_all_policy_topics_and_order_ownership():
    a = EmporioAgent(SOURCE, authenticator=Authenticator({hashlib.sha256(b'synthetic-test-token-customer-2-only').hexdigest(): 2}))
    try:
        assert a.store.db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 65
        assert a.store.db.execute('SELECT COUNT(*) FROM customers').fetchone()[0] == 50
        assert a.store.db.execute('SELECT COUNT(*) FROM orders').fetchone()[0] == 20
        for topic in POLICIES:
            assert 'Store manual' in a.policies.lookup(topic)[0], topic
            assert a.policies.retrieve(topic)[0].text
        assert '/login' in a.reply('order 8').text
        assert a.authenticate('synthetic-test-token-customer-2-only')
        assert 'shipped' in a.reply('order 8').text
        assert a.reply('order 1').text == a.reply('order 99999').text
        assert 'R$ 2.199,00' in a.reply('What is the price of Takamine GD20?').text
    finally:
        a.close()


@pytest.mark.skipif(not SOURCE, reason='Set EMPORIO_SOURCE_DIR to inspect modified original policy PDF')
def test_original_pdf_changed_without_heading_change_is_rejected(tmp_path):
    source = next(Path(SOURCE).glob('*.pdf'))
    (tmp_path / source.name).write_bytes(source.read_bytes() + b'\n% policy changed\n')
    with pytest.raises(ValueError, match='Unreviewed'):
        PolicyBook(tmp_path)
