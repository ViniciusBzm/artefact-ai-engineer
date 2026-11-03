# Architecture and design rationale

## Responsibilities

| Module | Responsibility |
|---|---|
| `cli.py` | Text interaction, explicit LLM mode, login and source tracing |
| `agent.py` | Privacy boundary, tool execution, context and factual rendering |
| `router.py` | Real Responses API request or explicitly selected offline classification |
| `store.py` | CSV contracts, read-only SQLite queries and Decimal pricing |
| `policy.py` | Pinned source loading, section/page retrieval and reviewed English answers |
| `security.py` | Opaque support-token verification and trusted local principal |
| `budget.py` | Optional persistent verification allowance and usage reconciliation |
| `evaluation.py` | Per-turn route, factual and privacy assertions |

## Public request flow

1. The CLI passes a message to the agent.
2. Length/privacy checks reject or withhold detected personal data and secrets before external routing. Explicit order identifiers follow the local authorization path.
3. In LLM mode, the model receives the current public request, previous category/model, up to four tool/source pairs and strict function schemas. Raw order data, customer tables, policy passages and tool-result bodies are not sent.
4. The model chooses exactly one function: `find_products`, `get_product`, `consult_policy`, `order_status`, `greeting` or `out_of_scope`.
5. Python validates tool name, required/extra properties, enums, text limits and finite numeric bounds. No model-provided identity, SQL or write operation can be executed.
6. A fixed local query or policy lookup returns the facts. Python renders the answer and source trace.

Each public request uses one tool-selection call followed by local execution. This fits the data size and makes the business rules testable, with one main intent per turn and constrained response wording.

## Prompt strategy

Instructions separate intent selection from factual execution. User text and session context are untrusted; the model selects a function. Catalog searches put instrument type in `category`, price in `max_price` and only an explicit brand/model in `keywords`. Short PIX/stock follow-ups use the previous product through `get_product`, while general payment questions use policy retrieval. Accessory requests select the dedicated accessories policy. Current-message intent takes priority over earlier context.

The API uses a pinned model, `store=False`, strict schemas, `tool_choice=required`, `parallel_tool_calls=False`, a 1,200-output-token cap, a 20-second timeout and zero SDK retries. Code validates the call, and local ownership checks remain authoritative. Model errors are explicit; optional fallback is labeled as offline.

## Prices and availability

Availability requires active product status and positive stock. Brand-only ambiguity asks for clarification; an unknown model is not substituted silently. Catalog filters retain brand/category and show at most eight matching available options.

Only `is_active` promotions apply; absent campaign dates cannot be inferred. Multiple active offers for one product fail closed. Decimal uses `ROUND_HALF_UP`. For example, list price R$ 2.399,00 with an 18% promotion yields R$ 1.967,18. The PIX discount does not stack. A non-promotional R$ 2.199,00 model costs R$ 2.089,05 with the explicit 5% PIX rule.

Order totals are shown as recorded, independently of current catalog pricing. Conflicting narrative product specifications are not offered as verified facts.

## Policy retrieval

`PolicyBook.retrieve` loads the page/section for a reviewed topic and attaches its source digest. Customer-facing text is a fixed reviewed English translation. Direct section retrieval keeps this short manual inspectable without an embedding service. The bundled English extract preserves the monetary conditions and delivery windows used in answers. Payment answers cite both page 3 and the non-stacking rule on page 6.

The original PDF is byte-hash pinned. The demo text fixture normalizes LF/CRLF only. Modified policy content fails closed until reviewed summaries, fingerprints and tests are updated. Conflicting installment tiers, shipping at exactly R$500 and inconsistent contact details are made explicit.

## Order security

A trusted operator maps a high-entropy token hash to a customer ID outside chat. The model cannot supply identity arguments. Every order query uses both order ID and authenticated customer ID. Denials do not distinguish another customer's order from a missing order.

Explicit order IDs and results stay local. Detected personal input is withheld from external routing. Reset/logout clear context and identity. Five failed login attempts lock the process-local authenticator; resetting does not reset this counter. Production use would require proper identity, expiry/revocation and shared rate limits.

## Evidence and scope

Offline classification is reproducible. Mocked SDK transport checks protocol behavior and validation; recorded API conversations demonstrate language interpretation and tool use. See [validation](VALIDATION.md) for the results and their evaluation scope, and [limitations](LIMITATIONS.md) for the prototype boundaries.
