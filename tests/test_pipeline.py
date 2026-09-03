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


def test_run_fetch_without_datasets_preserves_full_behavior(tmp_path, patch_resolver):
    """Regression pin: omitting `datasets` must fetch/report every dataset
    type, exactly like before the --datasets filter existed."""
    patch_resolver(FakeAdapter())
    config = FinPipeConfig(data_dir=tmp_path)

    result = pipeline_module.run_fetch("FAKE", config)

    reported_types = {o.dataset_type for o in result.outcomes}
    assert reported_types == set(pipeline_module.DATASET_FETCH_METHODS) | {DatasetType.METADATA}


def test_run_fetch_with_datasets_filter_only_reports_selected_types(tmp_path, patch_resolver):
    patch_resolver(FakeAdapter())
    config = FinPipeConfig(data_dir=tmp_path)

    result = pipeline_module.run_fetch("FAKE", config, datasets={DatasetType.PRICE})

    reported_types = {o.dataset_type for o in result.outcomes}
    assert reported_types == {DatasetType.METADATA, DatasetType.PRICE}


def test_run_fetch_datasets_filter_still_reports_not_supported_for_selected_type(
    tmp_path, patch_resolver
):
    """Selecting a type the adapter doesn't support still reports it as
    not_supported, scoped to just that type -- no crash, no silent skip."""
    patch_resolver(FakeAdapter())
    config = FinPipeConfig(data_dir=tmp_path)

    result = pipeline_module.run_fetch("FAKE", config, datasets={DatasetType.DIVIDENDS})

    outcome = next(o for o in result.outcomes if o.dataset_type == DatasetType.DIVIDENDS)
    assert outcome.status == "not_supported"
    reported_types = {o.dataset_type for o in result.outcomes}
    assert reported_types == {DatasetType.METADATA, DatasetType.DIVIDENDS}


def test_run_fetch_datasets_filter_only_saves_selected_frames_locally(tmp_path, patch_resolver):
    patch_resolver(FakeAdapter())
    config = FinPipeConfig(data_dir=tmp_path)

    pipeline_module.run_fetch("FAKE", config, datasets={DatasetType.PRICE})

    instrument_dir = tmp_path / "equity" / "FAKE"
    assert (instrument_dir / "price.csv").exists()
    assert not (instrument_dir / "dividends.csv").exists()
