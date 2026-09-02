"""Core data models shared by every source, storage backend, and exporter.

These types are the boundary between "source data" (whatever shape a given
provider's SDK returns) and the rest of FinPipe. Nothing outside a source
adapter should ever touch a provider-specific object directly -- everything
downstream works with `InstrumentMetadata` and `NormalizedDataset` only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

import pandas as pd


class DatasetType(str, Enum):
    """The kinds of datasets FinPipe knows how to model.

    Not every asset supports every dataset type, and not every source
    implements every type either -- see `SourceAdapter.SUPPORTED_DATASETS`.
    """

    METADATA = "metadata"
    PRICE = "price"
    DIVIDENDS = "dividends"
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASHFLOW = "cashflow"
    FUNDAMENTALS = "fundamentals"
    MACRO_SERIES = "macro_series"


@dataclass
class InstrumentMetadata:
    """Normalized identity/descriptive info for one instrument.

    Fields are intentionally optional where they don't apply to every asset
    class (e.g. `exchange`/`country` are meaningless for a macro series).
    """

    symbol: str
    name: Optional[str]
    asset_type: str
    source: str
    exchange: Optional[str] = None
    currency: Optional[str] = None
    country: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "asset_type": self.asset_type,
            "source": self.source,
            "exchange": self.exchange,
            "currency": self.currency,
            "country": self.country,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InstrumentMetadata":
        return cls(
            symbol=data["symbol"],
            name=data.get("name"),
            asset_type=data["asset_type"],
            source=data["source"],
            exchange=data.get("exchange"),
            currency=data.get("currency"),
            country=data.get("country"),
        )


@dataclass
class NormalizedDataset:
    """A single normalized, tabular dataset for one instrument."""

    dataset_type: DatasetType
    symbol: str
    source: str
    frame: pd.DataFrame


FetchStatus = Literal["fetched", "not_supported", "no_data", "error"]


@dataclass
class FetchOutcome:
    """Per-dataset result of a fetch attempt, used to render the CLI summary."""

    dataset_type: DatasetType
    status: FetchStatus
    detail: Optional[str] = None


@dataclass
class FetchResult:
    """Everything produced by one `core.pipeline.run_fetch()` call."""

    metadata: InstrumentMetadata
    outcomes: list[FetchOutcome] = field(default_factory=list)
    saved_dir: Optional[str] = None
    sheets_export_detail: Optional[str] = None
