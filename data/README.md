# Dataset provenance and privacy

- `demo/products.csv`, `categories.csv` and `promotions.csv` contain the supplied non-personal catalog snapshots.
- `demo/customers.csv`, `orders.csv` and `order_items.csv` contain two entirely synthetic customers/orders for ownership tests. They do not preserve the original customer-order relationships. Contact and tracking values are test placeholders.
- `demo/policies_demo.json` is a reviewed English extract of the supplied manual, version 2.1. Source-page keys preserve the payment conditions, shipping thresholds, delivery windows and policy exceptions used in answers. Its fingerprint is pinned in `policy.py`.
- Optional original inputs belong under ignored `raw/`, never in the public repository. All six CSV schemas and references are checked locally. Customer contacts, payment details and free-text order notes are not kept in the serving database or sent to the model.

The demo supports a self-contained checkout without original private inputs. Its values are snapshots; they are not current operational facts. Original-source integration tests are optional and skip when their private input directory is absent.
