# 02 Product And Nonstacking Discount

Recorded by the executable **offline demonstration router (NO LLM)**.
Data: non-personal catalog snapshot and entirely synthetic customer/order fixtures. Responses are in English.

**Customer:** What is the price of Takamine GD20?

**Assistant:** Takamine GD20 Dreadnought Natural — R$ 2.199,00; 5 in stock. Prices and stock reflect the supplied snapshot. Anything else I can help you with?

*Tool path:* `get_product | offline rules (NO LLM)`

*Source:* products.csv, promotions.csv

---

**Customer:** And with PIX?

**Assistant:** Takamine GD20 Dreadnought Natural — R$ 2.199,00; 5 in stock. With the standard 5% PIX discount: R$ 2.089,05. Prices and stock reflect the supplied snapshot. Anything else I can help you with?

*Tool path:* `get_product | offline rules (NO LLM)`

*Source:* products.csv, promotions.csv

---

**Customer:** How much is the Crafter HT-100 with PIX?

**Assistant:** Crafter HT-100 Folk Aço Natural — R$ 1.967,18 (was R$ 2.399,00, 18% active promotion); 3 in stock. The additional 5% PIX discount cannot be combined with this promotion. Prices and stock reflect the supplied snapshot. Anything else I can help you with?

*Tool path:* `get_product | offline rules (NO LLM)`

*Source:* products.csv, promotions.csv

---
