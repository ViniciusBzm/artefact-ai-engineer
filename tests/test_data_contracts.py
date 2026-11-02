import csv
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from emporio.store import Store, read_tables

DATA = Path(__file__).resolve().parents[1] / 'data/demo'


def change_table(tmp_path, table, mutate):
    shutil.copytree(DATA, tmp_path / 'data')
    path = tmp_path / 'data' / f'{table}.csv'
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    mutate(rows)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return path.parent


@pytest.mark.parametrize('table,field,value', [
    ('products', 'price_brl', 'NaN'), ('products', 'price_brl', '-1'),
    ('products', 'stock_quantity', '-1'), ('products', 'status', 'available'),
    ('products', 'category_id', '999'), ('products', 'specs', 'not-json'),
    ('products', 'created_at', '2026-02-30'), ('products', 'price_brl', '1.234'),
    ('promotions', 'discount_percent', '101'), ('promotions', 'is_active', 'yes'),
    ('orders', 'customer_id', '9999'), ('orders', 'status', 'lost'),
    ('order_items', 'quantity', '0'), ('order_items', 'product_id', '9999'),
])
def test_invalid_contract_fails_closed_without_private_values(tmp_path, table, field, value):
    folder = change_table(tmp_path, table, lambda rows: rows[0].update({field: value}))
    with pytest.raises(ValueError):
        Store(folder)


def test_duplicate_primary_key_rejected(tmp_path):
    folder = change_table(tmp_path, 'products', lambda rows: rows.append(rows[0]))
    with pytest.raises(ValueError, match='Duplicate key'):
        Store(folder)


def test_conflicting_active_promotions_rejected(tmp_path):
    def duplicate(rows):
        source = next(r for r in rows if r['is_active'] == '1')
        rows.append({**source, 'promotion_id': '999'})
    folder = change_table(tmp_path, 'promotions', duplicate)
    with pytest.raises(ValueError, match='Multiple active'):
        Store(folder)


def test_same_width_but_wrong_header_rejected(tmp_path):
    shutil.copytree(DATA, tmp_path / 'data')
    path = tmp_path / 'data/products.csv'
    path.write_text(path.read_text(encoding='utf-8').replace('price_brl', 'evilprice', 1), encoding='utf-8')
    with pytest.raises(ValueError, match='schema'):
        Store(path.parent)


def test_serving_database_is_read_only():
    s = Store(DATA)
    try:
        with pytest.raises(sqlite3.OperationalError):
            s.db.execute('DELETE FROM products')
    finally:
        s.db.close()


def test_discontinued_and_future_stock_are_never_offered():
    s = Store(DATA)
    try:
        ids = {r['product_id'] for r in s.list_products(limit=15)}
        assert not ids & {113, 130, 136}
        assert not s.list_products(keywords='Bass 2X')
        assert not s.list_products(keywords='KA-ABP-CTG')
    finally:
        s.db.close()


def test_ambiguous_brand_and_substring_model_are_not_guessed():
    s = Store(DATA)
    try:
        assert s.match_product('Yamaha') is None
        assert s.match_product('Martin D-28')['product_id'] == 93
        assert s.match_product('Martin D-2') is None
        assert s.match_product('Takamine nonexistent') is None
    finally:
        s.db.close()


def test_discounted_price_controls_budget_inclusion():
    s = Store(DATA)
    try:
        result = s.list_products(category='Ukuleles', max_price=440, keywords='Ohana CK-20')
        assert len(result) == 1 and str(result[0]['final_price']) == '439.20'
        assert not s.list_products(category='Ukuleles', max_price=439.19, keywords='Ohana CK-20')
    finally:
        s.db.close()
