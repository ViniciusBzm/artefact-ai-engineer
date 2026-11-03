# Empório da Música — Customer-Service Agent

A Python text agent for a musical-instrument store. It answers catalog, price, stock, promotion, order and policy questions using supplied data snapshots and reviewed policy evidence.

OpenAI interprets each message and selects a structured tool. Python validates the call, queries the data, applies business rules and renders the factual answer. An optional offline mode supports demonstrations and regression checks without an API key.

Start with the recorded conversations: [catalog and follow-up](examples/01_catalog_under_budget.md), [promotion and PIX rules](examples/02_product_and_nonstacking_discount.md), [order access](examples/03_order_privacy_multiturn.md), [returns](examples/04_online_returns_policy.md) and [scope handling](examples/05_out_of_scope.md). Four use the real OpenAI API; the order example demonstrates local authorization.

## Installation and first conversation

Requires Python 3.10+. Recorded local verification used Windows/Python 3.12. CI is configured for Python 3.10/3.12 on Linux; inspect the repository's Actions tab for remote run results. Run from the project directory. The first commands below use the offline demo; the following section enables the model.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[all]"
.\.venv\Scripts\emporio.exe --question "What is the price of Takamine GD20?" --debug
.\.venv\Scripts\emporio.exe
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[all]'
emporio --question 'What is the price of Takamine GD20?' --debug
```

The lookup should return **R$ 2.199,00** from the supplied snapshot. Try a conversation: `What is the price of Takamine GD20?`, followed by `And with PIX?`. The latter should return **R$ 2.089,05**. `/reset` clears context and signs out; `/exit` closes the session. `--debug` shows the tool path and source references.

The default demo data is self-contained. A minimal offline install is `python -m pip install -e .`; the `llm`, `pdf` and `test` extras install their respective dependencies. [Tested direct versions](requirements-tested.txt) are provided, but are not a transitive lockfile. `.env.example` is a reference and is not automatically loaded.

## Real LLM mode

Provider: OpenAI Responses API. Pinned model: `gpt-5.4-mini-2026-03-17`. Configure an application API key with Responses access and API billing. In PowerShell, the following prompt hides the key and keeps its value out of command history:

```powershell
$taskApiKey = Read-Host "OpenAI API key" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $taskApiKey).Password
$taskApiKey = $null
$env:OPENAI_MODEL = "gpt-5.4-mini-2026-03-17"
.\.venv\Scripts\emporio.exe --llm --question "What is the price of Takamine GD20?" --debug
# Interactive conversation:
.\.venv\Scripts\emporio.exe --llm
```

The optional Windows helper `& .\scripts\configure_openai_key.ps1` saves the key in ignored `.local/openai_api_key.txt` for the verification runner. Protect this plaintext file with OS permissions and remove it after use. The interactive CLI reads `OPENAI_API_KEY` from the environment.

```powershell
# Preflight only: no provider call
.\.venv\Scripts\python.exe scripts\run_live_checks.py

# Optional paid checks, only when intentionally requested:
.\.venv\Scripts\python.exe scripts\run_live_checks.py --run
.\.venv\Scripts\python.exe scripts\run_live_checks.py --run --full-suite
```

`--run` performs one smoke call; `--run --full-suite` selects five real integration cases and the 26-scenario evaluation. The runner applies a persistent local spending allowance and request pacing; see [verification controls](docs/VALIDATION.md). Direct CLI calls use the allowance only when `EMPORIO_LIVE_BUDGET_FILE` is configured. Provider errors are visible, and optional `--allow-fallback` is labeled as offline.

## Architecture and decisions

```text
CLI message → privacy boundary → LLM tool selection or explicit offline router
                              → strict tool/argument validation
                              → read-only catalog/pricing or policy retrieval
                              → Python response with source trace
Explicit order IDs → local authentication and ownership query → Python response
```

- **Python and SQLite:** six small tables do not require a distributed agent framework. Queries are fixed and parameterized; the serving database is read-only. No arbitrary SQL, shell or write tool is exposed to the model.
- **LLM function calling:** strict tool schemas, one required function call and local validation make interpretation inspectable. The model receives public input and bounded tool context. Python supplies factual prices and authorization decisions. A small pinned model keeps the routing task economical and versioned.
- **Deterministic answers:** Python renders queried facts and reviewed policy text. This constrains phrasing and planning, but prevents model-generated prices, invented order states and fabricated action confirmations.
- **Policy retrieval:** the selected topic retrieves reviewed pages/sections and their source digest. The short manual supports direct section retrieval without an embedding service. Answers use reviewed English translations with citations; changed source fingerprints require review before reuse.
- **Decimal pricing:** `ROUND_HALF_UP` makes cent rounding explicit. Only active promotions apply, and PIX never stacks with promotional discounts.
- **Session memory:** only the last category/model and four tool/source pairs are retained. Raw transcripts and order results are not saved in session history.

See [architecture and prompt strategy](docs/ARCHITECTURE.md) for the request flow, tradeoffs and security boundary.

## Data and order access

The [demo dataset](data/README.md) contains the supplied non-personal catalog/promotions, two entirely synthetic customers/orders and a reduced English policy fixture. All six CSV schemas, domains, identifiers and references are validated. Customer contacts, order notes and payment details are omitted from the serving database.

Knowing an order number or email does not authorize access. For a local demonstration, a trusted operator can create a support token for synthetic customer 2:

```powershell
.\.venv\Scripts\python.exe scripts\create_local_token.py --customer-id 2
.\.venv\Scripts\emporio.exe --auth-file .local\auth_tokens.json --login --question "order 8"
```

Enter the displayed token through the hidden login prompt. Only its SHA256 hash is stored. Every order query enforces both order ID and the authenticated customer ID; another customer's order and a nonexistent order receive the same denial. This operator utility must not be exposed as customer self-service.

To use separately supplied original files, place the six CSVs and `políticas_da_loja.pdf` under ignored `data/raw/` and pass `--data-dir data/raw`. Both short and supplied long CSV names are supported. The reviewed original PDF fingerprint must match. Private originals are not required to reproduce the public demo.

## Tests, evaluation and examples

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m emporio.evaluation --output .local\evaluation.json
.\.venv\Scripts\python.exe -m emporio.audit data/demo
.\.venv\Scripts\python.exe examples\generate_examples.py
```

Live tests require both `RUN_LIVE_LLM=1` and `OPENAI_API_KEY`; the opt-in runner sets them for its subprocesses. Two optional original-source checks require `EMPORIO_SOURCE_DIR`. Without private sources or live opt-in, those seven cases skip. Mocked HTTP tests exercise the real SDK serializer, errors, timeouts and invalid calls without contacting a provider.

[Validation evidence](docs/VALIDATION.md) records the current regression checks, the newly recorded live conversations and the earlier full LLM evaluation. The fixed evaluation covers 26 scenarios and 28 turns.

The five English conversations linked above contain actual messages, answers and tool/source traces. The [execution receipt](docs/examples_llm.json) records seven validated provider calls and four local order-security turns. To record another live set, run `python examples/generate_examples.py --llm` with `OPENAI_API_KEY` configured; this makes seven billable requests. Running the generator without `--llm` writes offline examples to `.local/examples-offline/` and preserves the published live transcripts.

## Limitations and future work

The agent handles one primary intent per turn and bounded follow-ups. Data is a snapshot, not live stock or carrier information. It cannot refund, cancel, determine individual return eligibility, register complaints or notify a person. It explains the limitation and the relevant support path. Policy contradictions are disclosed rather than resolved by invention.

The input PII guard is heuristic; the token identity mechanism is a local prototype without expiry or distributed rate limiting. `store=False` does not guarantee zero provider retention. See [known limitations](docs/LIMITATIONS.md).

With more time: broaden multilingual and adversarial evaluation, integrate a production identity provider and live operational APIs, add reviewed policy updates and monitoring, then consider a web interface.

## AI assistance

OpenAI Codex supported development, testing and documentation. Changes were validated through the tests and reviews documented in this repository.

## API references

- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Pinned model](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create)
