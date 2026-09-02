import pytest

from finpipe.core import resolver
from finpipe.core.exceptions import UnsupportedInstrument
from finpipe.sources.yahoo import YahooSource


def test_plain_symbol_resolves_to_yahoo():
    adapter, symbol = resolver.resolve("6758.T")
    assert isinstance(adapter, YahooSource)
    assert symbol == "6758.T"


def test_crypto_symbol_resolves_to_yahoo_unchanged():
    adapter, symbol = resolver.resolve("BTC-USD")
    assert isinstance(adapter, YahooSource)
    assert symbol == "BTC-USD"


def test_unregistered_source_prefix_raises_clear_error():
    with pytest.raises(UnsupportedInstrument, match="fred"):
        resolver.resolve("FRED:CPIAUCSL")
