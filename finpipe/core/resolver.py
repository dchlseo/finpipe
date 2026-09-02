"""Maps a raw CLI symbol to a source adapter + the symbol that adapter expects.

Adding a new source is meant to be two changes: register it in `_REGISTRY`
below, and implement its `SourceAdapter` in `finpipe/sources/`. Nothing else
in the app needs to change. See docs/architecture.md for a worked example
(a hypothetical `FRED:` source).
"""

from __future__ import annotations

from finpipe.core.exceptions import UnsupportedInstrument
from finpipe.sources.base import SourceAdapter
from finpipe.sources.yahoo import YahooSource

# Source registry. `SOURCE:CODE`-style symbols (e.g. "FRED:CPIAUCSL") select
# an entry by prefix; anything else defaults to "yahoo".
_REGISTRY: dict[str, SourceAdapter] = {
    "yahoo": YahooSource(),
}

DEFAULT_SOURCE = "yahoo"


def resolve(raw_symbol: str) -> tuple[SourceAdapter, str]:
    """Return `(adapter, symbol)` for a raw CLI symbol.

    Raises `UnsupportedInstrument` if the symbol names a source prefix that
    isn't registered (e.g. `FRED:CPIAUCSL` in the current MVP).
    """
    raw_symbol = raw_symbol.strip()
    if ":" in raw_symbol:
        prefix, _, code = raw_symbol.partition(":")
        source_key = prefix.strip().lower()
        adapter = _REGISTRY.get(source_key)
        if adapter is None:
            raise UnsupportedInstrument(
                f"Source '{source_key}' is not implemented yet. "
                f"Available sources: {', '.join(sorted(_REGISTRY))}."
            )
        return adapter, code.strip()

    return _REGISTRY[DEFAULT_SOURCE], raw_symbol
