"""Tests for the yahoo.py normalization helpers, using hand-built objects
shaped like raw `yfinance` output -- no network access, no `yfinance` import
of live data required.
"""

import pandas as pd

from finpipe.sources.yahoo import (
    _map_asset_type,
    _snake_case,
    normalize_dividends,
    normalize_price_history,
    normalize_statement,
)


def test_map_asset_type_known_and_unknown():
    assert _map_asset_type("EQUITY") == "equity"
    assert _map_asset_type("CRYPTOCURRENCY") == "crypto"
    assert _map_asset_type(None) == "unknown"
    assert _map_asset_type("SOMETHING_NEW") == "unknown"


def test_snake_case():
    assert _snake_case("Total Revenue") == "total_revenue"
    assert _snake_case("Adj Close") == "adj_close"


def test_normalize_price_history_shapes_columns_and_sorts_ascending():
    idx = pd.to_datetime(["2024-01-03", "2024-01-02", "2024-01-01"])
    raw = pd.DataFrame(
        {
            "Open": [3.0, 2.0, 1.0],
            "High": [3.5, 2.5, 1.5],
            "Low": [2.9, 1.9, 0.9],
            "Close": [3.2, 2.2, 1.2],
            "Adj Close": [3.2, 2.2, 1.2],
            "Volume": [300, 200, 100],
        },
        index=idx,
    )
    raw.index.name = "Date"

    out = normalize_price_history(raw)

    assert list(out.columns)[:2] == ["date", "open"]
    assert "adj_close" in out.columns
    assert out["date"].tolist() == sorted(out["date"].tolist())
    assert out.iloc[0]["close"] == 1.2


def test_normalize_price_history_empty_returns_none():
    assert normalize_price_history(pd.DataFrame()) is None
    assert normalize_price_history(None) is None


def test_normalize_dividends_shapes_two_columns():
    idx = pd.to_datetime(["2024-06-01", "2024-01-01"])
    raw = pd.Series([0.5, 0.4], index=idx, name="Dividends")

    out = normalize_dividends(raw)

    assert list(out.columns) == ["date", "dividend"]
    assert out["date"].tolist() == sorted(out["date"].tolist())


def test_normalize_dividends_empty_returns_none():
    assert normalize_dividends(pd.Series(dtype=float)) is None
    assert normalize_dividends(None) is None


def test_normalize_statement_transposes_and_snake_cases():
    cols = pd.to_datetime(["2024-12-31", "2023-12-31"])
    raw = pd.DataFrame(
        {cols[0]: [1000.0, 200.0], cols[1]: [900.0, 150.0]},
        index=["Total Revenue", "Net Income"],
    )

    out = normalize_statement(raw)

    assert "period_end" in out.columns
    assert "total_revenue" in out.columns
    assert "net_income" in out.columns
    assert out["period_end"].tolist() == sorted(out["period_end"].tolist())
    assert out.loc[out["period_end"] == cols[1], "total_revenue"].iloc[0] == 900.0


def test_normalize_statement_empty_returns_none():
    assert normalize_statement(pd.DataFrame()) is None
    assert normalize_statement(None) is None
