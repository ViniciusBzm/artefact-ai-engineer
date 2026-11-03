# Validation and reproducibility

## Current verification — 3 November 2026

| Check | Result |
|---|---|
| Public-fixture test suite | 138 passed, 7 skipped: 5 opt-in live cases and 2 requiring original inputs |
| Original-source integration | Both optional checks passed separately against the supplied CSVs and PDF |
| Recorded conversations | Five conversations, 11 customer turns: seven validated OpenAI calls and four local order-security turns |
| Offline evaluation | 26/26 scenarios, all 28 turns checked |
| CLI and data contracts | Product lookup and six-table audit passed |

The [verification receipt](revision_verification.json) records these checks and the [current application hashes](application_source_sha256.json). The five conversations in [examples/](../examples/) show actual messages, responses and tool/source traces. Their [execution receipt](examples_llm.json) includes the selected tools and token usage; provider response IDs are retained privately.

The bundled policy extract was checked against manual version 2.1, pages 2–8. Regression tests now verify that installment and shipping amounts in answers also occur in the cited passages. The catalog instructions explicitly separate instrument categories, price ceilings and brand/model filters.

## Final integration verification — 3 November 2026

All seven opt-in checks passed on commit `3759ff4` using `gpt-5.4-mini-2026-03-17`. The five live tests ran first, followed by the two checks against the original private files. The application and test source files were unchanged during execution.

| Test | Result | API calls | Input tokens | Output tokens | Estimated USD |
|---|---|---:|---:|---:|---:|
| Product lookup | Passed | 1 | 651 | 21 | 0.00058275 |
| Product and PIX follow-up | Passed | 2 | 1317 | 47 | 0.00119925 |
| Catalog and budget follow-up | Passed | 2 | 1307 | 56 | 0.00123225 |
| Returns and opening-hours conversation | Passed | 2 | 1318 | 38 | 0.00115950 |
| Mixed model/local-order session | Passed | 2 | 1317 | 47 | 0.00119925 |
| Original files: policy topics and order ownership | Passed | 0 | 0 | 0 | 0 |
| Modified original PDF rejected | Passed | 0 | 0 | 0 | 0 |

Total: **9 validated API calls, 5,910 input tokens and 209 output tokens; estimated cost USD 0.00537300**. The spending guard accounted for USD 0.0067162500 including its 25% margin. The original-file checks made zero API calls.

Costs use the configured rates of USD 0.75 per million input tokens and USD 4.50 per million output tokens, charging all input at the full input rate. They are token-based estimates. The existing reserve/settle mechanism, seven-second spacing, zero SDK retries and cumulative USD 1 allowance were retained; the nine additional attempts were explicitly authorized.

The [per-test and per-call receipt](final_integration_verification.json) records the seven results, usage and estimates. Private inputs, credentials and provider response IDs are excluded. The standard suite keeps these checks opt-in; their default skip status is separate from this successful execution.

## Earlier full live evaluation — 2 November 2026

| Check | Recorded result |
|---|---|
| Real integration | 5/5 cases passed: product lookup, three multi-message conversations and a mixed model/local-order session |
| Real agent evaluation | 26/26 scenarios, 28 checked turns and 23 validated provider calls |
| Package coverage | 712/783 statements (90.93%); 251/292 branches (85.96%) |

These results describe the earlier implementation, before the policy-extract and catalog-instruction corrections. Its [evaluation receipt](evaluation_llm.json) and [source manifest](https://github.com/ViniciusBzm/artefact-ai-engineer/blob/c1ddc41f30bccf0bc689986d8ac244a4b9eb1d46/docs/application_source_sha256.json) remain available. The current live evidence includes the nine-call integration run and the seven-call conversation recording above. Both runs used OpenAI Responses API with `gpt-5.4-mini-2026-03-17` and fallback disabled. Evaluation covers fixed case-study scenarios; broader language and adversarial testing remain future work.

## Repeat local checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m emporio.evaluation --output .local\evaluation.json
.\.venv\Scripts\python.exe -m emporio.audit data/demo
.\.venv\Scripts\python.exe examples\generate_examples.py
```

These commands run without an API key. The example generator writes offline transcripts to `.local/examples-offline/`, preserving the published live set. Private-source checks use `EMPORIO_SOURCE_DIR`. The five full live integration cases require `RUN_LIVE_LLM=1` and `OPENAI_API_KEY`. Mocked HTTP tests cover serialization, timeouts, 401/429/500 responses, malformed calls and forbidden arguments.

To record the current live examples again, configure `OPENAI_API_KEY` and run `python examples/generate_examples.py --llm`. It makes seven provider requests, validates every turn and replaces the transcripts only after the complete set passes. Its execution receipt defaults to ignored `.local/examples-run.json`. To use the spending guard, point `EMPORIO_LIVE_BUDGET_FILE` at a ledger initialized by the verification runner.

For package coverage, run `python -m coverage run -m pytest -q`, `python -m coverage combine`, then `python -m coverage report`.

## Optional live verification controls

`scripts/run_live_checks.py` defaults to credential/dependency preflight. `--run` performs one smoke request; `--run --full-suite` runs live integration followed by evaluation. SDK retries are disabled, requests are spaced seven seconds by default, and a provider or validation failure stops that stage.

The runner normally uses a persistent USD 1 allowance shared across subprocesses, with an 80-attempt ceiling. The final integration run used a separately authorized nine-attempt extension after that ceiling was reached; its receipt reports the cumulative ledger. Each request reserves the model's 400,000-token context plus 1,200 output tokens at the configured rates with a 25% margin. Reported usage reconciles the reservation; missing usage retains it. Re-running preserves the ledger, and file locking prevents competing writers.

The guard supports the explicitly priced pinned model. Review rates before changing the model or reusing the runner. Its scope is requests using `EMPORIO_LIVE_BUDGET_FILE`; direct CLI calls need that configuration. Request pacing is process-local. The earlier publication checks remain in [export verification](export_verification.json).
