# 04 Online Returns Policy

Recorded by the executable **offline demonstration router (NO LLM)**.
Data: non-personal catalog snapshot and entirely synthetic customer/order fixtures. Responses are in English.

**Customer:** I regret my online purchase. Can I return it?

**Assistant:** For online purchases, you may request a change-of-mind return within 7 calendar days of receiving the product. Keep the original packaging, manuals and accessories, without signs of use. The store covers return shipping and refunds via the original payment method within 10 business days. We need the delivery date and purchase channel to assess your specific case. [Store manual, p. 4] Was the purchase online, and on what date did you receive the item?

*Tool path:* `consult_policy | offline rules (NO LLM)`

*Source:* store policy page(s) 4; sha256 56beafcc4406

---

**Customer:** What is shipping for exactly R$ 500?

**Assistant:** Within the Campo Grande metropolitan region, shipping is free above R$ 500 and costs R$ 35 below that amount; exactly R$ 500 is unspecified and needs confirmation from our team. The stated delivery estimate is 1-3 business days. Outside the region, PAC is estimated at 5-12 business days, SEDEX at 2-5 and Jadlog at 3-8. Cost depends on destination and item dimensions; large instruments may need a special quote. These are policy estimates, not a promised arrival date. [Store manual, pp. 4, 5]

*Tool path:* `consult_policy | offline rules (NO LLM)`

*Source:* store policy page(s) 4, 5; sha256 56beafcc4406

---
