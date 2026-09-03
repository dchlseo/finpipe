"""FinPipe command-line interface.

Deliberately thin: parses arguments, calls `core.pipeline.run_fetch`, and
renders the result. All real logic lives in `core/`, `sources/`,
`storage/`, and `exporters/`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from finpipe.core.config import load_config
from finpipe.core.exceptions import FinPipeError
from finpipe.core.models import DatasetType, FetchResult
from finpipe.core.pipeline import run_fetch

_LABELS: dict[DatasetType, str] = {
    DatasetType.METADATA: "metadata",
    DatasetType.PRICE: "price",
    DatasetType.INCOME_STATEMENT: "income statement (annual)",
    DatasetType.INCOME_STATEMENT_QUARTERLY: "income statement (quarterly)",
    DatasetType.BALANCE_SHEET: "balance sheet (annual)",
    DatasetType.BALANCE_SHEET_QUARTERLY: "balance sheet (quarterly)",
    DatasetType.CASHFLOW: "cash flow (annual)",
    DatasetType.CASHFLOW_QUARTERLY: "cash flow (quarterly)",
    DatasetType.DIVIDENDS: "dividends",
    DatasetType.FUNDAMENTALS: "fundamentals",
    DatasetType.MACRO_SERIES: "macro series",
}

# Matches the order shown in the README/spec; metadata always first.
_DISPLAY_ORDER = [
    DatasetType.METADATA,
    DatasetType.PRICE,
    DatasetType.INCOME_STATEMENT,
    DatasetType.INCOME_STATEMENT_QUARTERLY,
    DatasetType.BALANCE_SHEET,
    DatasetType.BALANCE_SHEET_QUARTERLY,
    DatasetType.CASHFLOW,
    DatasetType.CASHFLOW_QUARTERLY,
    DatasetType.DIVIDENDS,
    DatasetType.FUNDAMENTALS,
    DatasetType.MACRO_SERIES,
]

# `metadata` is always fetched and isn't a selectable --datasets value.
_SELECTABLE_DATASETS = [d for d in DatasetType if d != DatasetType.METADATA]
_SELECTABLE_VALUES = {d.value for d in _SELECTABLE_DATASETS}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="finpipe", description="Fetch, normalize, and store financial/economic data."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch data for one instrument symbol.")
    fetch_parser.add_argument(
        "symbol", help="Instrument symbol, e.g. 6758.T, GOOGL, 005930.KS, BTC-USD."
    )
    fetch_parser.add_argument(
        "--local",
        action="store_true",
        help="Save locally. Local save always happens in the MVP; this flag is accepted "
        "for explicitness and has no additional effect.",
    )
    fetch_parser.add_argument(
        "--sheets",
        action="store_true",
        help="Also export to Google Sheets (requires configuration; see README).",
    )
    fetch_parser.add_argument(
        "--config", type=Path, default=None, help="Path to config.yaml (default: ./config.yaml)."
    )
    fetch_parser.add_argument(
        "--datasets",
        nargs="+",
        metavar="DATASET",
        default=None,
        help="Only fetch these dataset types (space-separated), e.g. "
        "--datasets price dividends. Default: fetch everything the source supports. "
        f"Valid values: {', '.join(sorted(_SELECTABLE_VALUES))}.",
    )
    return parser


def _parse_dataset_selection(names: Optional[list[str]]) -> Optional[set[DatasetType]]:
    """Validate and convert `--datasets` values to a `DatasetType` set.

    Returns `None` (meaning "fetch everything") when `names` is `None`, so
    the default no-`--datasets` behavior is unchanged.
    """
    if names is None:
        return None
    invalid = [n for n in names if n not in _SELECTABLE_VALUES]
    if invalid:
        raise FinPipeError(
            f"Unknown dataset name(s): {', '.join(invalid)}. "
            f"Valid options: {', '.join(sorted(_SELECTABLE_VALUES))}."
        )
    return {DatasetType(n) for n in names}


def _print_summary(result: FetchResult) -> None:
    meta = result.metadata
    print(f"Instrument: {meta.name or '(name unavailable)'}")
    print(f"Symbol: {meta.symbol}")
    print(f"Asset type: {meta.asset_type}")
    print()
    print("Fetched:")

    outcomes_by_type = {o.dataset_type: o for o in result.outcomes}
    for dataset_type in _DISPLAY_ORDER:
        outcome = outcomes_by_type.get(dataset_type)
        if outcome is None:
            continue
        label = _LABELS[dataset_type]
        if outcome.status == "fetched":
            print(f"✓ {label}")
        elif outcome.status == "not_supported":
            print(f"- {label} (not supported by source)")
        elif outcome.status == "no_data":
            print(f"- {label} (no data available)")
        else:
            print(f"x {label} (error: {outcome.detail})")

    print()
    print("Saved:")
    print(f"{result.saved_dir}{os.sep}")

    if result.sheets_export_detail is not None:
        print()
        if result.sheets_export_detail == "ok":
            print("Google Sheets: exported")
        else:
            print(f"Google Sheets: {result.sheets_export_detail}")


def _cmd_fetch(args: argparse.Namespace) -> int:
    try:
        selected_datasets = _parse_dataset_selection(args.datasets)
        config = load_config(args.config)
        result = run_fetch(
            args.symbol, config, export_to_sheets=args.sheets, datasets=selected_datasets
        )
    except FinPipeError as exc:
        print(f"Error: {exc}")
        return 1

    _print_summary(result)
    return 0


def main(argv: list[str] | None = None) -> int:
    # Some terminals (notably Windows consoles on a non-UTF-8 code page)
    # can't encode the ✓ glyphs used in the summary; force UTF-8 output
    # where possible rather than crashing after a successful fetch.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "fetch":
        return _cmd_fetch(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
