"""The contract every source adapter implements.

Nothing outside a source adapter subclass should import a provider SDK
(`yfinance`, a future FRED client, etc.) directly. Everything downstream --
the pipeline, storage, exporters, CLI -- only ever sees `InstrumentMetadata`
and plain `pandas.DataFrame`s, so a source can be replaced or added without
touching the rest of the application. See docs/architecture.md for the
rationale and a walkthrough of adding a new source.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from finpipe.core.models import DatasetType, InstrumentMetadata


class SourceAdapter(ABC):
    """Base class for a data source.

    `SUPPORTED_DATASETS` declares what this source is *capable* of
    producing, regardless of whether a particular symbol has data for it.
    The pipeline uses it to distinguish "not supported by this source"
    from "supported, but no data for this symbol" (the latter is signaled
    by a fetch method returning `None`).
    """

    name: str
    SUPPORTED_DATASETS: set[DatasetType] = set()

    @abstractmethod
    def fetch_metadata(self, symbol: str) -> InstrumentMetadata:
        """Fetch instrument identity/descriptive metadata.

        Raises `SourceError` if the symbol cannot be resolved at all
        (e.g. an invalid ticker) -- this is the one fetch that is fatal
        to the whole run.
        """

    def fetch_price(self, symbol: str) -> Optional[pd.DataFrame]:
        raise NotImplementedError

    def fetch_dividends(self, symbol: str) -> Optional[pd.DataFrame]:
        raise NotImplementedError

    def fetch_income_statement(self, symbol: str) -> Optional[pd.DataFrame]:
        raise NotImplementedError

    def fetch_balance_sheet(self, symbol: str) -> Optional[pd.DataFrame]:
        raise NotImplementedError

    def fetch_cashflow(self, symbol: str) -> Optional[pd.DataFrame]:
        raise NotImplementedError

    def fetch_fundamentals(self, symbol: str) -> Optional[pd.DataFrame]:
        raise NotImplementedError

    def fetch_macro_series(self, symbol: str) -> Optional[pd.DataFrame]:
        raise NotImplementedError


# Maps each non-metadata dataset type to the SourceAdapter method that
# produces it. The pipeline drives this table so adding a DatasetType only
# means adding one entry here plus the method on the adapters that support it.
DATASET_FETCH_METHODS: dict[DatasetType, str] = {
    DatasetType.PRICE: "fetch_price",
    DatasetType.DIVIDENDS: "fetch_dividends",
    DatasetType.INCOME_STATEMENT: "fetch_income_statement",
    DatasetType.BALANCE_SHEET: "fetch_balance_sheet",
    DatasetType.CASHFLOW: "fetch_cashflow",
    DatasetType.FUNDAMENTALS: "fetch_fundamentals",
    DatasetType.MACRO_SERIES: "fetch_macro_series",
}
