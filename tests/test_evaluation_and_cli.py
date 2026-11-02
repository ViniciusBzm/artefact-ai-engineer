import os
from pathlib import Path
import subprocess
import sys
import hashlib
import json

import pytest

from emporio.evaluation import evaluate
from emporio.router import budget

ROOT = Path(__file__).resolve().parents[1]


def test_offline_agent_evaluation_scenarios():
    report = evaluate()
    assert report['cases'] >= 20
    assert report['failed'] == 0, [r for r in report['results'] if not r['passed']]


@pytest.mark.parametrize('query,expected', [
    ('7-string guitars under R$ 1.000', 1000),
    ('under 1000.50', 1000.5), ('até R$ 1.000,50', 1000.5),
    ('under 500', 500), ('Yamaha C40', None), ('order 8', None),
])
def test_budget_is_extracted_from_price_cue_not_model_number(query, expected):
    assert budget(query) == expected


def cli(*args, stdin=None, env=None):
    process_env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONUTF8='1')
    if env:
        process_env.update(env)
    return subprocess.run([sys.executable, '-m', 'emporio.cli', *args], cwd=ROOT,
                          input=stdin, text=True, encoding='utf-8', capture_output=True, env=process_env)


def test_offline_cli_runs_the_real_entrypoint():
    result = cli('--question', 'What is the price of Takamine GD20?', '--debug')
    assert result.returncode == 0 and 'R$ 2.199,00' in result.stdout
    assert 'NO LLM' in result.stdout and 'products.csv' in result.stdout


def test_cli_rejects_missing_llm_credentials():
    result = cli('--llm', '--question', 'hello', env={'OPENAI_API_KEY': ''})
    assert result.returncode == 2 and 'requires OPENAI_API_KEY' in result.stderr


def test_cli_reset_and_exit():
    result = cli(stdin='Hello\n/reset\norder 8\n/exit\n')
    assert result.returncode == 0 and 'signed out' in result.stdout
    assert '/login' in result.stdout and 'shipped' not in result.stdout


def test_cli_missing_data_is_a_controlled_error(tmp_path):
    result = cli('--data-dir', str(tmp_path), '--question', 'hello')
    assert result.returncode == 2 and 'Traceback' not in result.stderr


def test_cli_local_login_executes_ownership_check(tmp_path, monkeypatch, capsys):
    from emporio.cli import main
    token = 'synthetic-test-token-customer-2-only'
    config = tmp_path / 'auth_tokens.json'
    config.write_text(json.dumps({hashlib.sha256(token.encode()).hexdigest(): 2}))
    monkeypatch.setattr('getpass.getpass', lambda prompt: token)
    monkeypatch.setattr(sys, 'argv', ['emporio', '--auth-file', str(config), '--login', '--question', 'order 8'])
    main()
    text = capsys.readouterr().out
    assert 'Signed in.' in text and 'shipped' in text and token not in text


def test_token_provisioning_writes_only_hash(tmp_path):
    path = tmp_path / 'auth_tokens.json'
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/create_local_token.py'),
                             '--customer-id', '2', '--output', str(path)], capture_output=True, text=True)
    assert result.returncode == 0
    token = result.stdout.splitlines()[1]
    contents = path.read_text()
    assert len(token) >= 32 and token not in contents
    assert json.loads(contents) == {hashlib.sha256(token.encode()).hexdigest(): 2}
