"""Orchestrates resolve -> fetch -> save -> (optional) export.

This is the only module that knows about all the pieces at once; it stays
deliberately thin -- each step's real logic lives in its own module.
"""

from __future__ import annotations

from finpipe.core import resolver
from finpipe.core.config import FinPipeConfig
from finpipe.core.exceptions import DatasetUnavailable, ExportError
from finpipe.core.models import DatasetType, FetchOutcome, FetchResult
from finpipe.exporters.google_sheets import GoogleSheetsExporter
from finpipe.sources.base import DATASET_FETCH_METHODS
from finpipe.storage.local import LocalStorage


def run_fetch(raw_symbol: str, config: FinPipeConfig, export_to_sheets: bool = False) -> FetchResult:
    adapter, symbol = resolver.resolve(raw_symbol)

    # Fatal if this fails -- an invalid ticker means there's nothing to save.
    metadata = adapter.fetch_metadata(symbol)

    storage = LocalStorage(config.data_dir)
    outcomes: list[FetchOutcome] = [FetchOutcome(DatasetType.METADATA, "fetched")]
    fetched_frames = {}

    for dataset_type, method_name in DATASET_FETCH_METHODS.items():
        if dataset_type not in adapter.SUPPORTED_DATASETS:
            outcomes.append(FetchOutcome(dataset_type, "not_supported"))
            continue
        try:
            frame = getattr(adapter, method_name)(symbol)
        except DatasetUnavailable as exc:
            outcomes.append(FetchOutcome(dataset_type, "no_data", str(exc)))
            continue
        except Exception as exc:  # unexpected failure fetching one dataset
            outcomes.append(FetchOutcome(dataset_type, "error", str(exc)))
            continue

        if frame is None or frame.empty:
            outcomes.append(FetchOutcome(dataset_type, "no_data"))
            continue

        outcomes.append(FetchOutcome(dataset_type, "fetched"))
        fetched_frames[dataset_type] = frame

    storage.save_metadata(metadata)
    for dataset_type, frame in fetched_frames.items():
        storage.save_dataset(metadata, dataset_type, frame)

    result = FetchResult(
        metadata=metadata,
        outcomes=outcomes,
        saved_dir=str(storage.instrument_dir(metadata)),
    )

    if export_to_sheets:
        try:
            GoogleSheetsExporter(config).export(metadata, fetched_frames)
            result.sheets_export_detail = "ok"
        except ExportError as exc:
            result.sheets_export_detail = f"skipped: {exc}"

    return result
