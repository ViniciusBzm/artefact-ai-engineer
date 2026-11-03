import importlib.util
from pathlib import Path

import pytest

from emporio.router import Router


def load_generator():
    path = Path(__file__).resolve().parents[1] / 'examples/generate_examples.py'
    spec = importlib.util.spec_from_file_location('example_generator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_recording_preserves_modes_and_local_order_boundary(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    out = tmp_path / 'examples'
    result = load_generator().generate_examples(output_dir=out, receipt_path=tmp_path / 'receipt.json')
    assert len(list(out.glob('*.md'))) == 5
    assert result['validated_provider_calls'] == 0
    assert result['local_security_turns'] == 4
    assert 'Offline demonstration' in (out / '01_catalog_under_budget.md').read_text()
    assert 'Local order authorization' in (out / '03_order_privacy_multiturn.md').read_text()
    assert 'cannot be combined' in (out / '02_product_and_nonstacking_discount.md').read_text()


def test_missing_credentials_leave_existing_examples_untouched(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    path = tmp_path / '01_catalog_under_budget.md'
    path.write_text('existing verified transcript')
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        load_generator().generate_examples(use_llm=True, output_dir=tmp_path, receipt_path=tmp_path / 'receipt.json')
    assert path.read_text() == 'existing verified transcript'


def test_llm_recording_rejects_missing_provider_evidence_before_writing(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-not-sent-to-a-provider')

    def unverified(self, *args):
        self.last_evidence = {'validated': True}
        return 'find_products', {'category': 'Violões', 'max_price': 1000, 'keywords': ''}, 'LLM tool call (test)'

    monkeypatch.setattr(Router, 'route', unverified)
    path = tmp_path / '01_catalog_under_budget.md'
    path.write_text('existing verified transcript')
    with pytest.raises(RuntimeError, match='provider evidence'):
        load_generator().generate_examples(use_llm=True, output_dir=tmp_path, receipt_path=tmp_path / 'receipt.json')
    assert path.read_text() == 'existing verified transcript'
