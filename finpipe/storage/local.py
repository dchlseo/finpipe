"""Local filesystem storage: JSON for metadata, CSV for tabular datasets.

Layout: `<base_dir>/<asset_type>/<symbol>/{metadata.json, <dataset_type>.csv, ...}`

No empty placeholder files are ever written -- a dataset that is `None` or
empty is simply skipped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from finpipe.core.models import DatasetType, InstrumentMetadata
from finpipe.core.paths import safe_symbol

# Financial statements are split into annual/quarterly subfolders rather than
# flat files. The filename stem is deliberately decoupled from
# `dataset_type.value` (e.g. "balance_sheet", not "balance_sheet_quarterly")
# -- the subfolder already encodes the period, so the filename stays the
# plain statement name in both.
_STATEMENT_LAYOUT: dict[DatasetType, tuple[str, str]] = {
    DatasetType.INCOME_STATEMENT: ("annual", "income_statement"),
    DatasetType.BALANCE_SHEET: ("annual", "balance_sheet"),
    DatasetType.CASHFLOW: ("annual", "cashflow"),
    DatasetType.INCOME_STATEMENT_QUARTERLY: ("quarterly", "income_statement"),
    DatasetType.BALANCE_SHEET_QUARTERLY: ("quarterly", "balance_sheet"),
    DatasetType.CASHFLOW_QUARTERLY: ("quarterly", "cashflow"),
}


class LocalStorage:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def instrument_dir(self, meta: InstrumentMetadata) -> Path:
        return self.base_dir / meta.asset_type / safe_symbol(meta.symbol)

    def save_metadata(self, meta: InstrumentMetadata) -> Path:
        target_dir = self.instrument_dir(meta)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / "metadata.json"
        path.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")
        return path

    def save_dataset(
        self, meta: InstrumentMetadata, dataset_type: DatasetType, frame: Optional[pd.DataFrame]
    ) -> Optional[Path]:
        if frame is None or frame.empty:
            return None
        instrument_dir = self.instrument_dir(meta)

        layout = _STATEMENT_LAYOUT.get(dataset_type)
        if layout is not None:
            subfolder, stem = layout
            target_dir = instrument_dir / subfolder
            filename = f"{stem}.csv"
            # These statements used to be saved flat at <instrument_dir>/<stem>.csv;
            # remove the old file so a stale duplicate isn't left behind once the
            # nested annual/quarterly file is written.
            old_flat_path = instrument_dir / filename
            if old_flat_path.exists():
                old_flat_path.unlink()
        else:
            target_dir = instrument_dir
            filename = f"{dataset_type.value}.csv"

        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        frame.to_csv(path, index=False)
        return path
