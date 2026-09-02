"""Verifies YahooSource conforms to the SourceAdapter contract using a fake
`yfinance.Ticker` -- no live network calls.
"""

import pandas as pd
import pytest

from finpipe.core.exceptions import SourceError
from finpipe.core.models import DatasetType
from finpipe.sources import yahoo as yahoo_module
from finpipe.sources.yahoo import YahooSource


class FakeTicker:
    def __init__(self, info, history=None, dividends=None, income_stmt=None):
        self.info = info
        self._history = history if history is not None else pd.DataFrame()
        self.dividends = dividends if dividends is not None else pd.Series(dtype=float)
        self.income_stmt = income_stmt if income_stmt is not None else pd.DataFrame()
        self.balance_sheet = pd.DataFrame()
        self.cashflow = pd.DataFrame()

    def history(self, **kwargs):
        return self._history


@pytest.fixture
def patch_ticker(monkeypatch):
    def _patch(fake_ticker):
        monkeypatch.setattr(yahoo_module.yf, "Ticker", lambda symbol: fake_ticker)

    return _patch


def test_fetch_metadata_maps_quote_type(patch_ticker):
    fake = FakeTicker(info={"longName": "Sony Group Corporation", "quoteType": "EQUITY", "exchange": "TSE", "currency": "JPY", "country": "JP"})
    patch_ticker(fake)

    source = YahooSource()
    meta = source.fetch_metadata("6758.T")

    assert meta.name == "Sony Group Corporation"
    assert meta.asset_type == "equity"
    assert meta.exchange == "TSE"
    assert meta.source == "yahoo"


def test_fetch_metadata_crypto_has_no_exchange(patch_ticker):
    fake = FakeTicker(info={"shortName": "Bitcoin USD", "quoteType": "CRYPTOCURRENCY", "currency": "USD"})
    patch_ticker(fake)

    meta = YahooSource().fetch_metadata("BTC-USD")

    assert meta.asset_type == "crypto"
    assert meta.exchange is None
    assert meta.country is None


def test_fetch_metadata_invalid_symbol_raises_source_error(patch_ticker):
    patch_ticker(FakeTicker(info={}))

    with pytest.raises(SourceError):
        YahooSource().fetch_metadata("NOT-A-REAL-TICKER")


def test_fetch_dividends_missing_returns_none(patch_ticker):
    patch_ticker(FakeTicker(info={"longName": "X"}, dividends=pd.Series(dtype=float)))

    assert YahooSource().fetch_dividends("BTC-USD") is None


def test_fetch_price_returns_normalized_frame(patch_ticker):
    idx = pd.to_datetime(["2024-01-01"])
    hist = pd.DataFrame({"Open": [1.0], "High": [1.1], "Low": [0.9], "Close": [1.05], "Volume": [100]}, index=idx)
    hist.index.name = "Date"
    patch_ticker(FakeTicker(info={"longName": "X"}, history=hist))

    frame = YahooSource().fetch_price("GOOGL")

    assert frame is not None
    assert "date" in frame.columns
    assert "close" in frame.columns


def test_yahoo_supported_datasets_excludes_macro_and_fundamentals():
    assert DatasetType.MACRO_SERIES not in YahooSource.SUPPORTED_DATASETS
    assert DatasetType.FUNDAMENTALS not in YahooSource.SUPPORTED_DATASETS
    assert DatasetType.PRICE in YahooSource.SUPPORTED_DATASETS
