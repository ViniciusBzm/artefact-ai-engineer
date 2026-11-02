"""Read-only, parameterized SQL access to the case study's CSV snapshots."""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re
import sqlite3
import unicodedata

REQUIRED = ("categories", "products", "promotions", "customers", "orders", "order_items")
SCHEMAS = {
    "categories": "category_id name description",
    "products": "product_id price_brl name category_id description stock_quantity status specs created_at",
    "promotions": "promotion_id product_id discount_percent description is_active",
    "customers": "customer_id name phone email city",
    "orders": "order_id customer_id order_date status total_brl payment_method tracking_code estimated_delivery notes",
    "order_items": "order_id quantity product_id",
}


def read_tables(path: Path) -> dict[str, list[dict]]:
    """Validate full source contracts before building any serving tables.

    Errors identify the table/row/field, never the field's private value.
    Customer contact fields are validated here but not retained by Store.
    """
    tables = {}
    optional = {"phone", "tracking_code", "estimated_delivery", "notes"}
    domains = {("products", "status"): {"active", "discontinued", "coming_soon"},
               ("orders", "status"): {"pending", "confirmed", "shipped", "delivered", "cancelled"},
               ("promotions", "is_active"): {"0", "1"}}
    for table in REQUIRED:
        matches = sorted(p for p in path.glob("*.csv") if p.name.endswith(f"{table}.csv"))
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one CSV for {table}; found {len(matches)}")
        with matches[0].open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            expected = SCHEMAS[table].split()
            if reader.fieldnames is None or len(reader.fieldnames) != len(expected) or set(reader.fieldnames) != set(expected):
                raise ValueError(f"Unexpected schema for {table}")
            records = list(reader)
        if not records:
            raise ValueError(f"Empty dataset: {table}")
        for index, row in enumerate(records, 2):
            for field in expected:
                value = row.get(field)
                try:
                    if value is None or None in row or (not value.strip() and field not in optional):
                        raise ValueError()
                    if field.endswith("_id") or field in {"quantity", "stock_quantity", "discount_percent"}:
                        integer = int(value)
                        if str(integer) != value or integer < (0 if field in {"stock_quantity", "discount_percent"} else 1):
                            raise ValueError()
                        if field == "discount_percent" and integer > 100:
                            raise ValueError()
                    if field in {"price_brl", "total_brl"}:
                        amount = Decimal(value)
                        if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('.01')):
                            raise ValueError()
                    if (table, field) in domains and value not in domains[table, field]:
                        raise ValueError()
                    if field in {"created_at", "order_date", "estimated_delivery"} and value:
                        date.fromisoformat(value)
                    if field == "specs" and not isinstance(json.loads(value), dict):
                        raise ValueError()
                except (ValueError, TypeError, ArithmeticError) as exc:
                    raise ValueError(f"Invalid {table} row {index} field {field}") from exc
        keys = [tuple(r[c] for c in (["order_id", "product_id"] if table == "order_items" else [expected[0]])) for r in records]
        if len(set(keys)) != len(keys):
            raise ValueError(f"Duplicate key in {table}")
        tables[table] = records
    for child, key, parent in [("products", "category_id", "categories"), ("promotions", "product_id", "products"),
                               ("orders", "customer_id", "customers"), ("order_items", "order_id", "orders"),
                               ("order_items", "product_id", "products")]:
        parents = {r[key] for r in tables[parent]}
        if any(r[key] not in parents for r in tables[child]):
            raise ValueError(f"Orphan reference: {child}.{key}")
    active = [r["product_id"] for r in tables["promotions"] if r["is_active"] == "1"]
    if len(active) != len(set(active)):
        raise ValueError("Multiple active promotions for one product require review")
    return tables


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value).lower())
    return "".join(c for c in value if not unicodedata.combining(c))


def brl(value: str | int | float | Decimal) -> str:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"R$ {amount:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def discounted(price: str | float, rate: int) -> Decimal:
    return (Decimal(str(price)) * (Decimal(100 - rate) / Decimal(100))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


class Store:
    """Fresh in-memory snapshot: no SQL generated by the language model."""

    def __init__(self, data_dir: str | Path):
        self.path = Path(data_dir)
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self._load()

    def _source(self, table: str) -> Path:
        matches = sorted(p for p in self.path.glob("*.csv") if p.name.endswith(f"{table}.csv"))
        if len(matches) != 1:
            raise FileNotFoundError(f"Expected one CSV ending in '{table}.csv' in {self.path}; found {len(matches)}")
        return matches[0]

    def _load(self) -> None:
        tables = read_tables(self.path)
        ddl = """
        CREATE TABLE categories (category_id INTEGER PRIMARY KEY, name TEXT, description TEXT);
        CREATE TABLE products (product_id INTEGER PRIMARY KEY, price_brl TEXT, name TEXT,
            category_id INTEGER, description TEXT, stock_quantity INTEGER, status TEXT, specs TEXT, created_at TEXT);
        CREATE TABLE promotions (promotion_id INTEGER PRIMARY KEY, product_id INTEGER,
            discount_percent INTEGER, description TEXT, is_active INTEGER);
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY);
        CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT, status TEXT,
            total_brl TEXT, tracking_code TEXT, estimated_delivery TEXT);
        CREATE TABLE order_items (order_id INTEGER, quantity INTEGER, product_id INTEGER);
        CREATE INDEX idx_products_category ON products(category_id);
        CREATE INDEX idx_promotions_product ON promotions(product_id);
        CREATE INDEX idx_orders_customer ON orders(customer_id);
        """
        self.db.executescript(ddl)
        for table in REQUIRED:
            records = tables[table]
            cols = ["customer_id"] if table == "customers" else SCHEMAS[table].split()
            if table == 'orders':
                cols = [c for c in cols if c not in {'payment_method', 'notes'}]
            sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
            self.db.executemany(sql, [[r[col] for col in cols] for r in records])
        self.db.commit()
        self.db.execute("PRAGMA query_only = ON")

    def _catalog_rows(self) -> list[dict]:
        rows = self.db.execute("""
            SELECT p.product_id, p.name, p.price_brl, p.stock_quantity, p.status,
                   c.name AS category,
                   (SELECT MAX(pr.discount_percent) FROM promotions pr
                    WHERE pr.product_id = p.product_id AND pr.is_active = 1) AS discount
            FROM products p JOIN categories c ON c.category_id = p.category_id
        """).fetchall()
        items = []
        for row in rows:
            entry = dict(row)
            entry["discount"] = int(entry["discount"] or 0)
            entry["final_price"] = discounted(entry["price_brl"], entry["discount"])
            items.append(entry)
        return items

    def list_products(self, category: str = "", max_price: float | None = None,
                      keywords: str = "", limit: int = 8) -> list[dict]:
        """Filters a full CSV snapshot by availability and effective promotional price."""
        limit = max(1, min(int(limit), 15))
        tokens = [norm(t) for t in keywords.split() if len(t) > 1]
        result = []
        for item in self._catalog_rows():
            if item["status"] != "active" or int(item["stock_quantity"]) <= 0:
                continue
            if category and norm(category) not in norm(item["category"]):
                continue
            if max_price is not None and item["final_price"] > Decimal(str(max_price)):
                continue
            if tokens and not all(t in norm(item["name"]) for t in tokens):
                continue
            result.append(item)
        result.sort(key=lambda x: (x["final_price"], norm(x["name"])))
        return result[:limit]

    def match_product(self, query: str) -> dict | None:
        """Return only an unambiguous model match; brand-only queries must clarify."""
        words = [w for w in re.findall(r"[a-z0-9]+", norm(query)) if len(w) > 1 and
                 w not in {"quanto", "custa", "preco", "valor", "do", "da", "de", "o", "a", "me", "diga", "sobre", "qual", "tem", "voces", "um", "uma", "modelo", "em", "estoque", "esta", "disponivel", "produto", "no", "pix", "com", "cartao", "disponibilidade", "gostaria", "saber", "quero", "venda", "the", "price", "of", "is", "how", "much", "do", "you", "have", "for", "in", "stock", "and", "please", "what", "does", "with", "cost", "available", "availability"}]
        if not words:
            return None
        candidates = []
        for p in self._catalog_rows():
            name = set(re.findall(r"[a-z0-9]+", norm(p["name"])))
            overlap = sum(1 for w in words if w in name)
            if overlap == len(words) and overlap >= 1:
                candidates.append((overlap, len(p["name"]), p))
        if len(candidates) != 1:
            return None
        candidates.sort(key=lambda x: (-x[0], x[1]))
        return candidates[0][2]

    def get_order(self, order_id: int, customer_id: int | None) -> dict | None:
        """Trusted caller supplies the authenticated principal, never a chat identifier."""
        if type(customer_id) is not int or customer_id <= 0:
            return None
        row = self.db.execute("""
            SELECT o.order_id, o.order_date, o.status, o.total_brl, o.tracking_code,
                   o.estimated_delivery
            FROM orders o WHERE o.order_id=? AND o.customer_id=?
        """, (int(order_id), customer_id)).fetchone()
        if row is None:
            return None
        result = dict(row)
        products = self.db.execute("""
            SELECT p.name, oi.quantity FROM order_items oi
            JOIN products p ON oi.product_id=p.product_id WHERE oi.order_id=?
        """, (int(order_id),)).fetchall()
        result["items"] = [dict(p) for p in products]
        return result

    def status_count(self) -> dict:
        return {r[0]: r[1] for r in self.db.execute("SELECT status, COUNT(*) FROM products GROUP BY status")}
