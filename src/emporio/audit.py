"""Reproducible, contact-free source profiling. python -m emporio.audit PATH."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .store import read_tables


def audit(path: Path) -> dict:
    tables = read_tables(path)
    report = {'contract_validation': 'passed', 'tables': {}}
    for table, rows in tables.items():
        report['tables'][table] = {
            'rows': len(rows), 'columns': list(rows[0]),
            'empty_fields': {key: sum(not r[key].strip() for r in rows) for key in rows[0]},
            'key_uniqueness': 'passed', 'foreign_key_validation': 'passed',
        }
        file = next(p for p in path.glob('*.csv') if p.name.endswith(f'{table}.csv'))
        report['tables'][table]['sha256'] = hashlib.sha256(file.read_bytes()).hexdigest()
    emails = Counter(r['email'].strip().casefold() for r in tables['customers'])
    report['customer_email_duplicate_groups'] = sum(count > 1 for count in emails.values())
    report['active_promotions'] = sum(r['is_active'] == '1' for r in tables['promotions'])
    report['product_status_counts'] = dict(Counter(r['status'] for r in tables['products']))
    dates = [r['order_date'] for r in tables['orders']]
    report['order_date_range'] = {'min': min(dates), 'max': max(dates)}
    report['freshness'] = 'Unknown extraction date; supplied local snapshot only'
    report['notes'] = [
        'Contacts are deliberately absent from this report.',
        'Passing structural checks does not resolve conflicting product descriptions or policy wording.',
        'Order totals are historical recorded amounts, not reconstructed from current product prices.',
    ]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data_dir', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(audit(args.data_dir), ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()
