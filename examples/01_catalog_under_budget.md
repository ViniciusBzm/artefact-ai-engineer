# 01 Catalog Under Budget

Recorded by the executable **offline demonstration router (NO LLM)**.
Data: non-personal catalog snapshot and entirely synthetic customer/order fixtures. Responses are in English.

**Customer:** Show acoustic guitars under R$ 1000

**Assistant:** Here are up to 8 matching available option(s) (limited to 8) in Violões for up to R$ 1.000,00:
- Tagima Memphis AC-39 Nylon Natural — R$ 429,90; 15 in stock
- Rozini RC-104 Nylon Estudante — R$ 459,90; 10 in stock
- Shelby SN-100 Folk Aço Preto — R$ 549,00; 5 in stock
- Giannini GF-1R Aço Folk Sunburst — R$ 579,90; 7 in stock
- Yamaha C40 Nylon Natural — R$ 599,90; 12 in stock
- Giannini GN-15 Nylon Cedr Natural — R$ 689,00; 6 in stock
- Yamaha F310 Aço Natural — R$ 699,90; 14 in stock
- Tagima Dallas Tuner Aço Natural — R$ 749,00; 9 in stock

Prices and stock reflect the supplied dataset snapshot, not a live storefront.

*Tool path:* `find_products | offline rules (NO LLM)`

*Source:* products.csv, categories.csv, promotions.csv

---

**Customer:** And under R$ 500?

**Assistant:** Here are up to 2 matching available option(s) (limited to 8) in Violões for up to R$ 500,00:
- Tagima Memphis AC-39 Nylon Natural — R$ 429,90; 15 in stock
- Rozini RC-104 Nylon Estudante — R$ 459,90; 10 in stock

Prices and stock reflect the supplied dataset snapshot, not a live storefront.

*Tool path:* `find_products | offline rules (NO LLM)`

*Source:* products.csv, categories.csv, promotions.csv

---
