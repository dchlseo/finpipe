"""Safe filesystem path helpers for local storage.

Kept separate from `storage/local.py` so the sanitization rule is a single,
testable function rather than something implicit in the storage class.
"""

from __future__ import annotations

import re

_UNSAFE_CHARS = re.compile(r'[:\\/*?"<>|]')


def safe_symbol(symbol: str) -> str:
    """Make a symbol safe to use as a single path component.

    Most MVP symbols (`6758.T`, `005930.KS`, `BTC-USD`, `GOOGL`) need no
    change. Symbols with a source prefix (e.g. `FRED:CPIAUCSL`) have their
    `:` replaced so they remain a single, valid directory name.
    """
    return _UNSAFE_CHARS.sub("_", symbol.strip())
