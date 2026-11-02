"""Local identity boundary and conservative pre-provider privacy guard."""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import re

from .store import norm

EMAIL = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)


def contains_private_data(text: str) -> bool:
    """Conservative heuristic, not a general-purpose PII recognition guarantee."""
    t = norm(text)
    return bool(EMAIL.search(text) or
                re.search(r"(?<!\d)(?:\+?\d[\d .()\-/]{8,}\d)(?!\d)", text) or
                re.search(r"\b(my name|meu nome|me chamo|my address|meu endereco|my phone|meu telefone|cpf|password|senha|api[_ -]?key|token)\b", t) or
                re.search(r"\bsk-[a-zA-Z0-9_-]{12,}", text))


class Authenticator:
    """Trusted local config: SHA256 of a high-entropy token -> customer ID.

    Five failed attempts lock this object for its lifetime. This is a local CLI
    boundary, not an internet identity provider or distributed rate limiter.
    """
    def __init__(self, token_hashes: dict[str, int] | None = None):
        self._tokens = dict(token_hashes or {})
        if any(not re.fullmatch(r"[a-f0-9]{64}", digest) or type(cid) is not int or cid < 1
               for digest, cid in self._tokens.items()):
            raise ValueError("Invalid authentication configuration")
        self.failures = 0

    @classmethod
    def from_file(cls, path: str | Path | None) -> "Authenticator":
        if not path:
            return cls()
        content = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(content, dict):
            raise ValueError("Authentication configuration must be an object")
        return cls(content)

    def authenticate(self, token: str) -> int | None:
        if self.failures >= 5 or not isinstance(token, str) or not 32 <= len(token) <= 512:
            self.failures += 1
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        for expected, customer in self._tokens.items():
            if hmac.compare_digest(digest, expected):
                return customer
        self.failures += 1
        return None
