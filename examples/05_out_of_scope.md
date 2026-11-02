# 05 Out Of Scope

Recorded by the executable **offline demonstration router (NO LLM)**.
Data: non-personal catalog snapshot and entirely synthetic customer/order fixtures. Responses are in English.

**Customer:** What's the weather on Mars?

**Assistant:** I can help with musical instruments, product availability, orders and store policies. What would you like to know?

*Tool path:* `out_of_scope | offline rules (NO LLM)`

*Source:* none

---

**Customer:** Do you sell strings for acoustic guitars?

**Assistant:** We specialize in musical instruments only; we do not sell strings, picks, cables, cases, pedals or amplifiers. [Store manual, p. 6]

*Tool path:* `consult_policy | offline rules (NO LLM)`

*Source:* store policy page(s) 6; sha256 56beafcc4406

---

**Customer:** Where is the store?

**Assistant:** Our store is at Rua 14 de Maio, 3200, Centro, Campo Grande/MS, CEP 79202-333. You can reach the store at (67) 3341-4444. [Store manual, p. 2]

*Tool path:* `consult_policy | offline rules (NO LLM)`

*Source:* store policy page(s) 2; sha256 56beafcc4406

---
