"""Tests for `core.pipeline.run_fetch` orchestration, using a fake adapter --
no live network calls, no real source implementation involved.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import pytest

from finpipe.core import pipeline as pipeline_module
from finpipe.core.config import FinPipeConfig
from finpipe.core.models import DatasetType, InstrumentMetadata
from finpipe.sources.base import SourceAdapter


class FakeAdapter(SourceAdapter):
    name = "fake_source"
    SUPPORTED_DATASETS = {DatasetType.PRICE}

    def fetch_metadata(self, symbol: str) -> InstrumentMetadata:
        return InstrumentMetadata(symbol=symbol, name="Fake Instrument", asset_type="equity", source=self.name)

    def fetch_price(self, symbol: str) -> Optional[pd.DataFrame]:
        return pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "close": [1.0]})


@pytest.fixture
def patch_resolver(monkeypatch):
    def _patch(adapter, symbol="FAKE"):
        monkeypatch.setattr(pipeline_module.resolver, "resolve", lambda raw: (adapter, symbol))

    return _patch


def test_run_fetch_adds_source_column_to_saved_frame(tmp_path, patch_resolver):
    patch_resolver(FakeAdapter())
    config = FinPipeConfig(data_dir=tmp_path)

    result = pipeline_module.run_fetch("FAKE", config)

    price_path = tmp_path / "equity" / "FAKE" / "price.csv"
    assert price_path.exists()
    saved = pd.read_csv(price_path)
    assert saved["source"].tolist() == ["fake_source"]

    outcome = next(o for o in result.outcomes if o.dataset_type == DatasetType.PRICE)
    assert outcome.status == "fetched"


def test_run_fetch_reports_saved_dir_and_not_supported_datasets(tmp_path, patch_resolver):
    patch_resolver(FakeAdapter())
    config = FinPipeConfig(data_dir=tmp_path)

    result = pipeline_module.run_fetch("FAKE", config)

    assert result.saved_dir == str(tmp_path / "equity" / "FAKE")
    dividends_outcome = next(o for o in result.outcomes if o.dataset_type == DatasetType.DIVIDENDS)
    assert dividends_outcome.status == "not_supported"
