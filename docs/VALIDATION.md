# Validation and reproducibility

## Executed real-provider verification

The unchanged application source was verified on 2 November 2026 against OpenAI Responses API and pinned `gpt-5.4-mini-2026-03-17`, with fallback disabled:

| Check | Observed result |
|---|---|
| Real integration | 5/5 cases passed: one product lookup, three multi-message conversations and one mixed model/local-order session |
| Real agent evaluation | 26/26 scenarios, all 28 turns checked; 23 validated provider calls; remaining turns followed local security paths |
| Local suite with private original sources | 135 passed, 5 live cases skipped and executed separately |
| Public-fixture regression before this export | 133 passed, 7 skipped: 5 live and 2 requiring separately supplied private sources |
| Offline evaluation | 26/26 scenarios, all 28 turns checked, zero provider calls |
| Prior branch/subprocess coverage | 712/783 statements (90.93%); 251/292 branches (85.96%); package only |

These are measured fixed-fixture results, not production accuracy or a security certification. Live testing exposed PIX-follow-up and accessory-routing issues; instructions were corrected and the full verification was repeated successfully.

This documentation export did **not** make new provider calls. [Application hashes](application_source_sha256.json) bind the unchanged source files to the verified implementation. The [real evaluation receipt](evaluation_llm.json) retains validated tool calls and token usage; provider response identifiers were omitted from the public copy. Full original receipts remain local. The [offline receipt](evaluation_offline.json) clearly identifies rule-based execution.

The export's current local regression results are recorded in [export verification](export_verification.json). They are separate from the earlier live execution.

## Repeat local checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m emporio.evaluation --output .local\evaluation.json
.\.venv\Scripts\python.exe -m emporio.audit data/demo
.\.venv\Scripts\python.exe examples\generate_examples.py
```

No key is needed for those commands. Private-source tests require `EMPORIO_SOURCE_DIR`; live tests require both `RUN_LIVE_LLM=1` and `OPENAI_API_KEY`. Without these inputs, seven cases skip. The SDK mock transport exercises serialization, timeouts, 401/429/500 errors, malformed calls and forbidden arguments without provider access. Skipping, fallback and a successful preflight never establish live success.

For coverage, run `python -m coverage run -m pytest -q`, `python -m coverage combine`, then `python -m coverage report`. Scripts outside the application package are not included in the reported package percentage.

## Optional paid verification controls

`scripts/run_live_checks.py` defaults to credential/dependency preflight without API access. `--run` opts into one smoke request. `--run --full-suite` selects integration followed by evaluation. The first integration failure or provider/tool evaluation error stops that stage. SDK automatic retries are zero; requests are spaced seven seconds by default. This is process-local pacing, not an organization-wide daily/token limiter.

The runner uses a persistent local **USD 1 default verification allowance**, shared across its subprocesses, with an additional 80-attempt ceiling. Before each request it reserves the full 400,000-token model context plus 1,200 maximum output tokens, using the published input/output prices and a 25% margin. A valid usage receipt reconciles the reservation; missing or invalid usage retains it. Re-running does not reset the ledger. A file lock fails closed on competing writers or a stale lock after a crash.

Only the explicitly priced pinned model is supported by this guard. Review prices and assumptions before changing model or reusing the runner in a different environment. It does not control direct CLI traffic unless `EMPORIO_LIVE_BUDGET_FILE` is configured, other applications, taxes or account-wide usage. No credentials, account balances or payment data are distributed.
