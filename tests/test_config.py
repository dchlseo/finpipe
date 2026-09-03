"""Tests for `core.config.load_config`, in particular the optional
`google_sheets.worksheet_mapping` section.
"""

from __future__ import annotations

import pytest

from finpipe.core.config import load_config
from finpipe.core.exceptions import ConfigError
from finpipe.core.models import DatasetType


def _write_config(tmp_path, text: str):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def test_load_config_defaults_to_empty_worksheet_mapping_when_absent(tmp_path):
    config_path = _write_config(tmp_path, "data_dir: data\n")

    config = load_config(config_path)

    assert config.google_sheets_worksheet_mapping == {}


def test_load_config_defaults_to_empty_mapping_when_file_missing(tmp_path):
    config = load_config(tmp_path / "does-not-exist.yaml")
    assert config.google_sheets_worksheet_mapping == {}


def test_load_config_parses_valid_worksheet_mapping(tmp_path):
    config_path = _write_config(
        tmp_path,
        "google_sheets:\n"
        "  worksheet_mapping:\n"
        '    price: "99_DailyPriceData"\n'
        '    cashflow: "99_CashFlow"\n',
    )

    config = load_config(config_path)

    assert config.google_sheets_worksheet_mapping == {
        DatasetType.PRICE: "99_DailyPriceData",
        DatasetType.CASHFLOW: "99_CashFlow",
    }


def test_load_config_raises_config_error_on_unknown_dataset_key(tmp_path):
    # "cash_flow" (with underscore) is a common mistake -- the real enum
    # value is "cashflow".
    config_path = _write_config(
        tmp_path,
        "google_sheets:\n  worksheet_mapping:\n    cash_flow: \"99_CashFlow\"\n",
    )

    with pytest.raises(ConfigError) as exc_info:
        load_config(config_path)
    assert "cash_flow" in str(exc_info.value)


def test_load_config_raises_config_error_on_non_dict_mapping(tmp_path):
    config_path = _write_config(
        tmp_path, "google_sheets:\n  worksheet_mapping: \"not-a-dict\"\n"
    )

    with pytest.raises(ConfigError):
        load_config(config_path)
