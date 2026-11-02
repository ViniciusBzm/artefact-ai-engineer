"""Provision a local support token. Run only as the trusted dataset operator.

This utility is not customer self-service and must never be exposed as an API.
Only the hash is written. The generated token is displayed once locally.
"""
import argparse
import hashlib
import json
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--customer-id', type=int, required=True)
    parser.add_argument('--output', type=Path, default=Path('.local/auth_tokens.json'))
    args = parser.parse_args()
    if args.customer_id < 1:
        parser.error('customer ID must be positive')
    token = secrets.token_urlsafe(32)
    config = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else {}
    if not isinstance(config, dict):
        parser.error('existing auth configuration must be an object')
    config[hashlib.sha256(token.encode()).hexdigest()] = args.customer_id
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print('Keep this support token private; it is shown only now:')
    print(token)
    print(f'Hash configuration saved to {args.output}. Do not commit it.')


if __name__ == '__main__':
    main()
