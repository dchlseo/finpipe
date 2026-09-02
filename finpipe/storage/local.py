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
        target_dir = self.instrument_dir(meta)
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{dataset_type.value}.csv"
        frame.to_csv(path, index=False)
        return path
