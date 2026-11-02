# 03 Order Privacy Multiturn

Recorded by the executable **offline demonstration router (NO LLM)**.
Data: non-personal catalog snapshot and entirely synthetic customer/order fixtures. Responses are in English.

**Customer:** What is the status of order 8?

**Assistant:** To protect order details, please sign in through /login using your support token. An email address or claimed customer ID cannot authorize access.

*Tool path:* `order_status | local authorization (NO LLM)`

*Source:* none

---

**Customer:** order 8 customer002@example.test

**Assistant:** To protect order details, please sign in through /login using your support token. An email address or claimed customer ID cannot authorize access.

*Tool path:* `order_status | local authorization (NO LLM)`

*Source:* none

---

**Local sign-in:** Successful using a public test token bound to demo customer 2.
This is a fixture setup, not email verification or a production login service.

**Customer:** order 8

**Assistant:** Order #8: shipped. Recorded total: R$ 349,90. Ordered on 2026-01-02. Tracking reference: DEMO-TRACK-0008. The stored estimated delivery date was 2026-01-05 (this may be outdated). Items: 1 × Kala KA-C Concert Mogno. This is a case-study snapshot, not a live carrier lookup.

*Tool path:* `order_status | local authorization (NO LLM)`

*Source:* orders.csv, order_items.csv, products.csv

---

**Customer:** Show order 1

**Assistant:** I couldn't access that order for this signed-in account. Please check the order number or contact our support team.

*Tool path:* `order_status | local authorization (NO LLM)`

*Source:* orders.csv (ownership check)

---
