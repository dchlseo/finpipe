"""Yahoo Finance source adapter, backed by `yfinance`.

This is the ONLY module in FinPipe allowed to import `yfinance` or reason
about its dataframe/series shapes. Every public method returns either an
`InstrumentMetadata` or a normalized `pandas.DataFrame` (or `None` when the
symbol genuinely has no data for that dataset) -- never a raw `yfinance`
object.

Normalization rules applied here:
  * Price history: index reset to a `date` column (tz-naive), all other
    columns snake_cased, sorted ascending by date.
  * Dividends: the `yfinance` Series becomes a two-column `date, dividend`
    DataFrame.
  * Financial statements (income/balance/cashflow): `yfinance` returns
    line-items-as-rows and periods-as-columns; this is transposed so each
    row is a period (`period_end` column, tz-naive datetime) and each
    column is a line item, snake_cased from Yahoo's own label (e.g.
    "Total Revenue" -> "total_revenue"). Values are coerced to float.
    Yahoo's own line-item vocabulary is preserved rather than remapped to
    a custom accounting ontology -- see docs/architecture.md.
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd
import yfinance as yf

from finpipe.core.exceptions import DatasetUnavailable, SourceError
from finpipe.core.models import DatasetType, InstrumentMetadata
from finpipe.sources.base import SourceAdapter

_QUOTE_TYPE_MAP = {
    "EQUITY": "equity",
    "CRYPTOCURRENCY": "crypto",
    "ETF": "etf",
    "INDEX": "index",
    "MUTUALFUND": "mutual_fund",
    "CURRENCY": "currency",
    "FUTURE": "future",
}


def _map_asset_type(quote_type: Optional[str]) -> str:
    if not quote_type:
        return "unknown"
    return _QUOTE_TYPE_MAP.get(quote_type.upper(), "unknown")


def _snake_case(label: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", str(label).strip()).strip("_").lower()


def _tz_naive(series: pd.Series) -> pd.Series:
    series = pd.to_datetime(series)
    if getattr(series.dt, "tz", None) is not None:
        series = series.dt.tz_localize(None)
    return series


def normalize_price_history(hist: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if hist is None or hist.empty:
        return None
    out = hist.copy()
    out.index.name = "date"
    out = out.reset_index()
    out.columns = [c if c == "date" else _snake_case(c) for c in out.columns]
    out["date"] = _tz_naive(out["date"])
    return out.sort_values("date").reset_index(drop=True)


def normalize_dividends(dividends: Optional[pd.Series]) -> Optional[pd.DataFrame]:
    if dividends is None or dividends.empty:
        return None
    out = dividends.rename("dividend").reset_index()
    out.columns = ["date", "dividend"]
    out["date"] = _tz_naive(out["date"])
    out["dividend"] = pd.to_numeric(out["dividend"], errors="coerce")
    return out.sort_values("date").reset_index(drop=True)


def normalize_statement(statement: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if statement is None or statement.empty:
        return None
    out = statement.T.copy()
    out.index.name = "period_end"
    out = out.reset_index()
    out = out.rename(columns={c: _snake_case(c) for c in out.columns if c != "period_end"})
    out["period_end"] = _tz_naive(out["period_end"])
    for col in out.columns:
        if col != "period_end":
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.sort_values("period_end").reset_index(drop=True)


class YahooSource(SourceAdapter):
    """Source adapter for equities, ETFs, indices, and crypto via Yahoo Finance."""

    name = "yahoo"
    SUPPORTED_DATASETS = {
        DatasetType.METADATA,
        DatasetType.PRICE,
        DatasetType.DIVIDENDS,
        DatasetType.INCOME_STATEMENT,
        DatasetType.BALANCE_SHEET,
        DatasetType.CASHFLOW,
    }

    def _ticker(self, symbol: str) -> yf.Ticker:
        return yf.Ticker(symbol)

    def fetch_metadata(self, symbol: str) -> InstrumentMetadata:
        ticker = self._ticker(symbol)
        try:
            info = ticker.info or {}
        except Exception as exc:  # yfinance can raise a variety of errors
            raise SourceError(f"Could not fetch '{symbol}' from Yahoo Finance: {exc}") from exc

        name = info.get("longName") or info.get("shortName")
        has_identity = name or info.get("regularMarketPrice") is not None or info.get("symbol")
        if not has_identity:
            raise SourceError(
                f"'{symbol}' does not look like a valid Yahoo Finance symbol (no data returned)."
            )

        return InstrumentMetadata(
            symbol=symbol,
            name=name,
            asset_type=_map_asset_type(info.get("quoteType")),
            source=self.name,
            exchange=info.get("exchange"),
            currency=info.get("currency"),
            country=info.get("country"),
        )

    def fetch_price(self, symbol: str) -> Optional[pd.DataFrame]:
        ticker = self._ticker(symbol)
        try:
            hist = ticker.history(period="max", auto_adjust=False)
        except Exception as exc:
            raise DatasetUnavailable(f"price history unavailable: {exc}") from exc
        return normalize_price_history(hist)

    def fetch_dividends(self, symbol: str) -> Optional[pd.DataFrame]:
        ticker = self._ticker(symbol)
        try:
            dividends = ticker.dividends
        except Exception as exc:
            raise DatasetUnavailable(f"dividends unavailable: {exc}") from exc
        return normalize_dividends(dividends)

    def fetch_income_statement(self, symbol: str) -> Optional[pd.DataFrame]:
        return self._fetch_statement(symbol, "income_stmt")

    def fetch_balance_sheet(self, symbol: str) -> Optional[pd.DataFrame]:
        return self._fetch_statement(symbol, "balance_sheet")

    def fetch_cashflow(self, symbol: str) -> Optional[pd.DataFrame]:
        return self._fetch_statement(symbol, "cashflow")

    def _fetch_statement(self, symbol: str, attr: str) -> Optional[pd.DataFrame]:
        ticker = self._ticker(symbol)
        try:
            raw = getattr(ticker, attr)
        except Exception as exc:
            raise DatasetUnavailable(f"{attr} unavailable: {exc}") from exc
        return normalize_statement(raw)
