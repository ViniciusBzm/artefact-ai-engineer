# 03 Order Privacy Multiturn

Execution: Local order authorization and ownership checks.
Recorded at 2026-11-03T20:49:13.254188+00:00 (UTC).
Dataset: supplied catalog and synthetic customer/order records.

**Customer:** What is the status of order 8?

**Assistant:** To protect order details, please sign in through /login using your support token. An email address or claimed customer ID cannot authorize access.

*Tool path:* order_status | local authorization (NO LLM)

*Source:* none

---

**Customer:** order 8 customer002@example.test

**Assistant:** To protect order details, please sign in through /login using your support token. An email address or claimed customer ID cannot authorize access.

*Tool path:* order_status | local authorization (NO LLM)

*Source:* none

---

**Local sign-in:** Demo customer 2 authenticated through the local support-token mechanism.

**Customer:** order 8

**Assistant:** Order #8: shipped. Recorded total: R$ 349,90. Ordered on 2026-01-02. Tracking reference: DEMO-TRACK-0008. The stored estimated delivery date was 2026-01-05 (this may be outdated). Items: 1 × Kala KA-C Concert Mogno. This is a case-study snapshot, not a live carrier lookup.

*Tool path:* order_status | local authorization (NO LLM)

*Source:* orders.csv, order_items.csv, products.csv

---

**Customer:** Show order 1

**Assistant:** I couldn't access that order for this signed-in account. Please check the order number or contact our support team.

*Tool path:* order_status | local authorization (NO LLM)

*Source:* orders.csv (ownership check)

---
