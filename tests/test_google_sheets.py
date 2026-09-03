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
        # Every `update()` call, in order: (values, range_name, value_input_option).
        self.update_calls = []
        # Every `format()` call, in order: (range_name, format_dict).
        self.format_calls = []

    def clear(self):
        self.cleared = True

    def update(self, values, range_name=None, value_input_option=None):
        self.update_calls.append((values, range_name, value_input_option))
        if range_name is None:
            # Mirrors the real API: an unranged update rewrites the whole grid.
            self.updated_values = values

    def format(self, range_name, format_dict):
        self.format_calls.append((range_name, format_dict))


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


def test_export_price_dates_are_rewritten_with_user_entered_semantics(tmp_path, fake_spreadsheet):
    """The date column must be re-written with USER_ENTERED so Sheets stores
    it as a real date value rather than text -- otherwise MAX(), XLOOKUP(),
    YEAR(), EDATE() and friends silently fail on it (see bug report: `MAX()`
    returning 0 because the column was text).
    """
    config = _config(tmp_path)
    exporter = GoogleSheetsExporter(config)

    exporter.export(_meta(), {DatasetType.PRICE: _frame()})

    worksheet = fake_spreadsheet.worksheets_by_title["Price"]
    # Call 1: the full-grid write (default RAW). Call 2: the targeted,
    # date-only rewrite that upgrades just that column to a real date.
    assert len(worksheet.update_calls) == 2
    _, first_range, first_input_option = worksheet.update_calls[0]
    assert first_range is None
    assert first_input_option is None

    date_values, date_range, date_input_option = worksheet.update_calls[1]
    assert date_range == "A2:A2"
    assert date_values == [["2024-01-01"]]
    assert date_input_option == google_sheets_module.ValueInputOption.user_entered

    # Display format is pinned so it still reads as YYYY-MM-DD regardless of
    # the destination spreadsheet's locale.
    assert worksheet.format_calls == [
        ("A2:A2", {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}})
    ]


def test_export_keeps_numeric_values_numeric(tmp_path, fake_spreadsheet):
    config = _config(tmp_path)
    exporter = GoogleSheetsExporter(config)

    exporter.export(_meta(), {DatasetType.PRICE: _frame()})

    worksheet = fake_spreadsheet.worksheets_by_title["Price"]
    header, row = worksheet.updated_values
    assert header == ["date", "close"]
    assert row[1] == 1.0
    assert isinstance(row[1], float)


def test_export_keeps_text_values_as_text_and_unreparsed(tmp_path, fake_spreadsheet):
    """A numeric-looking text column (e.g. a zero-padded ticker/ID) must stay
    a plain string, and must never be swept up by the targeted date rewrite
    -- only the actual date column gets USER_ENTERED treatment.
    """
    config = _config(tmp_path)
    exporter = GoogleSheetsExporter(config)
    frame = pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-01"]), "ticker": ["007"]}
    )

    exporter.export(_meta(), {DatasetType.PRICE: frame})

    worksheet = fake_spreadsheet.worksheets_by_title["Price"]
    header, row = worksheet.updated_values
    assert header == ["date", "ticker"]
    assert row[1] == "007"
    assert isinstance(row[1], str)

    # Only column A (date) was ever re-written with a targeted range.
    ranged_calls = [range_name for _, range_name, _ in worksheet.update_calls if range_name]
    assert ranged_calls == ["A2:A2"]
