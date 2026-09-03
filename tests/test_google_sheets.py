"""Tests for `exporters.google_sheets.GoogleSheetsExporter` worksheet-title
resolution (defaults vs. configured overrides). `gspread` is faked entirely
-- no network calls.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from finpipe.core.config import FinPipeConfig
from finpipe.core.models import DatasetType, InstrumentMetadata
from finpipe.exporters import google_sheets as google_sheets_module
from finpipe.exporters.google_sheets import GoogleSheetsExporter


class FakeWorksheet:
    def __init__(self, title):
        self.title = title
        self.cleared = False
        self.updated_values = None

    def clear(self):
        self.cleared = True

    def update(self, values):
        self.updated_values = values


class FakeSpreadsheet:
    def __init__(self):
        self.worksheets_by_title = {}

    def worksheet(self, title):
        if title not in self.worksheets_by_title:
            raise google_sheets_module.gspread.WorksheetNotFound(title)
        return self.worksheets_by_title[title]

    def add_worksheet(self, title, rows, cols):
        worksheet = FakeWorksheet(title)
        self.worksheets_by_title[title] = worksheet
        return worksheet


class FakeClient:
    def __init__(self, spreadsheet):
        self._spreadsheet = spreadsheet

    def open_by_key(self, sheet_id):
        return self._spreadsheet


def _config(tmp_path, worksheet_mapping=None) -> FinPipeConfig:
    creds_path = tmp_path / "creds.json"
    creds_path.write_text("{}", encoding="utf-8")
    return FinPipeConfig(
        data_dir=tmp_path,
        google_sheet_id="sheet123",
        google_credentials_path=creds_path,
        google_sheets_worksheet_mapping=worksheet_mapping or {},
    )


def _meta() -> InstrumentMetadata:
    return InstrumentMetadata(symbol="6758.T", name="Sony", asset_type="equity", source="yahoo")


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "close": [1.0]})


@pytest.fixture
def fake_spreadsheet(monkeypatch, tmp_path):
    spreadsheet = FakeSpreadsheet()
    monkeypatch.setattr(
        google_sheets_module.gspread,
        "service_account",
        lambda filename: FakeClient(spreadsheet),
    )
    return spreadsheet


def test_export_uses_default_worksheet_titles_when_no_mapping_configured(
    tmp_path, fake_spreadsheet
):
    config = _config(tmp_path)
    exporter = GoogleSheetsExporter(config)

    exporter.export(_meta(), {DatasetType.PRICE: _frame()})

    assert "Price" in fake_spreadsheet.worksheets_by_title


def test_export_applies_custom_worksheet_title_override(tmp_path, fake_spreadsheet):
    config = _config(tmp_path, {DatasetType.PRICE: "99_DailyPriceData"})
    exporter = GoogleSheetsExporter(config)

    exporter.export(_meta(), {DatasetType.PRICE: _frame()})

    assert "99_DailyPriceData" in fake_spreadsheet.worksheets_by_title
    assert "Price" not in fake_spreadsheet.worksheets_by_title


def test_export_partial_override_leaves_other_defaults_intact(tmp_path, fake_spreadsheet):
    config = _config(tmp_path, {DatasetType.PRICE: "99_DailyPriceData"})
    exporter = GoogleSheetsExporter(config)

    exporter.export(
        _meta(),
        {DatasetType.PRICE: _frame(), DatasetType.DIVIDENDS: _frame()},
    )

    assert "99_DailyPriceData" in fake_spreadsheet.worksheets_by_title
    assert "Dividends" in fake_spreadsheet.worksheets_by_title


def test_export_skips_dataset_types_with_no_title_mapping(tmp_path, fake_spreadsheet):
    # Simulate a dataset type with no default title and no custom one --
    # export() should just skip it, not crash.
    config = _config(tmp_path)
    exporter = GoogleSheetsExporter(config)
    del exporter._worksheet_titles[DatasetType.MACRO_SERIES]

    exporter.export(_meta(), {DatasetType.MACRO_SERIES: _frame()})

    # "Metadata" is always written; the unmapped dataset type is not.
    assert set(fake_spreadsheet.worksheets_by_title) == {"Metadata"}
