"""Tests for `cli.py` argument parsing and `_cmd_fetch` wiring.

No network, no real `run_fetch`/`load_config` -- both are monkeypatched so
these stay fast, offline unit tests of the CLI layer only.
"""

from __future__ import annotations

import pytest

from finpipe import cli
from finpipe.core.exceptions import ConfigError, FinPipeError
from finpipe.core.models import DatasetType, FetchOutcome, FetchResult, InstrumentMetadata


def _fake_result() -> FetchResult:
    meta = InstrumentMetadata(symbol="FAKE", name="Fake Instrument", asset_type="equity", source="fake")
    return FetchResult(
        metadata=meta,
        outcomes=[FetchOutcome(DatasetType.PRICE, "fetched")],
        saved_dir="data/equity/FAKE",
    )


def test_build_parser_datasets_defaults_to_none():
    args = cli.build_parser().parse_args(["fetch", "GOOGL"])
    assert args.datasets is None


def test_build_parser_accepts_single_dataset():
    args = cli.build_parser().parse_args(["fetch", "GOOGL", "--datasets", "price"])
    assert args.datasets == ["price"]


def test_build_parser_accepts_multiple_datasets():
    args = cli.build_parser().parse_args(["fetch", "GOOGL", "--datasets", "price", "dividends"])
    assert args.datasets == ["price", "dividends"]


def test_parse_dataset_selection_returns_none_when_not_given():
    assert cli._parse_dataset_selection(None) is None


def test_parse_dataset_selection_converts_valid_names_to_enum_set():
    selected = cli._parse_dataset_selection(["price", "dividends"])
    assert selected == {DatasetType.PRICE, DatasetType.DIVIDENDS}


def test_parse_dataset_selection_raises_on_invalid_name_with_useful_message():
    with pytest.raises(FinPipeError) as exc_info:
        cli._parse_dataset_selection(["bogus"])
    message = str(exc_info.value)
    assert "bogus" in message
    assert "price" in message  # lists valid options


def test_parse_dataset_selection_raises_naming_only_the_invalid_token():
    with pytest.raises(FinPipeError) as exc_info:
        cli._parse_dataset_selection(["price", "bogus"])
    message = str(exc_info.value)
    assert "bogus" in message
    # The invalid-name list itself should not include the valid one.
    assert "Unknown dataset name(s): bogus" in message


def test_parse_dataset_selection_rejects_metadata():
    """`metadata` is always fetched implicitly and isn't a --datasets value."""
    with pytest.raises(FinPipeError):
        cli._parse_dataset_selection(["metadata"])


def test_cmd_fetch_passes_selected_datasets_through_to_run_fetch(monkeypatch):
    captured = {}

    def fake_run_fetch(symbol, config, export_to_sheets=False, datasets=None):
        captured["symbol"] = symbol
        captured["datasets"] = datasets
        return _fake_result()

    monkeypatch.setattr(cli, "run_fetch", fake_run_fetch)
    monkeypatch.setattr(cli, "load_config", lambda path: object())

    args = cli.build_parser().parse_args(["fetch", "FAKE", "--datasets", "price"])
    rc = cli._cmd_fetch(args)

    assert rc == 0
    assert captured["datasets"] == {DatasetType.PRICE}


def test_cmd_fetch_without_datasets_passes_none_through(monkeypatch):
    captured = {}

    def fake_run_fetch(symbol, config, export_to_sheets=False, datasets=None):
        captured["datasets"] = datasets
        return _fake_result()

    monkeypatch.setattr(cli, "run_fetch", fake_run_fetch)
    monkeypatch.setattr(cli, "load_config", lambda path: object())

    args = cli.build_parser().parse_args(["fetch", "FAKE"])
    cli._cmd_fetch(args)

    assert captured["datasets"] is None


def test_cmd_fetch_reports_invalid_dataset_name_cleanly(capsys):
    args = cli.build_parser().parse_args(["fetch", "FAKE", "--datasets", "bogus"])
    rc = cli._cmd_fetch(args)

    assert rc == 1
    assert "Error:" in capsys.readouterr().out


def test_cmd_fetch_catches_config_error_cleanly(monkeypatch, capsys):
    """Regression test: load_config() must run inside the try/except so a
    ConfigError (e.g. an invalid worksheet_mapping key) prints cleanly
    instead of propagating as a raw traceback."""

    def raise_config_error(path):
        raise ConfigError("bad config")

    monkeypatch.setattr(cli, "load_config", raise_config_error)

    args = cli.build_parser().parse_args(["fetch", "FAKE"])
    rc = cli._cmd_fetch(args)

    assert rc == 1
    assert "Error: bad config" in capsys.readouterr().out
