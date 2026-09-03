"""Configuration loading.

FinPipe works with zero configuration (local save just uses `./data`).
`config.yaml` (gitignored; copy from `config.example.yaml`) and environment
variables are both optional, additive ways to set the Google Sheets
destination and override the local data directory. Env vars win over the
config file so credentials never need to live in a committed file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from finpipe.core.exceptions import ConfigError
from finpipe.core.models import DatasetType

DEFAULT_DATA_DIR = "data"


@dataclass
class FinPipeConfig:
    data_dir: Path
    google_sheet_id: Optional[str] = None
    google_credentials_path: Optional[Path] = None
    google_sheets_worksheet_mapping: dict[DatasetType, str] = field(default_factory=dict)


def _parse_worksheet_mapping(raw: dict) -> dict[DatasetType, str]:
    """Parse the optional `google_sheets.worksheet_mapping` section.

    Keys must match a `DatasetType` value exactly (e.g. `cashflow`, not
    `cash_flow`); unrecognized keys raise `ConfigError` rather than being
    silently ignored, since a typo'd key would otherwise look like it worked.
    """
    mapping_raw = (raw.get("google_sheets") or {}).get("worksheet_mapping") or {}
    if not isinstance(mapping_raw, dict):
        raise ConfigError(
            "google_sheets.worksheet_mapping must be a mapping of dataset type to worksheet title."
        )

    valid_values = {d.value for d in DatasetType}
    result: dict[DatasetType, str] = {}
    bad_keys = []
    for key, title in mapping_raw.items():
        if key not in valid_values:
            bad_keys.append(str(key))
            continue
        result[DatasetType(key)] = str(title)

    if bad_keys:
        raise ConfigError(
            "Unknown dataset type(s) in google_sheets.worksheet_mapping: "
            f"{', '.join(sorted(bad_keys))}. Valid keys are: {', '.join(sorted(valid_values))}."
        )
    return result


def load_config(path: Optional[Path] = None) -> FinPipeConfig:
    """Load config from `path` (default `./config.yaml`), then apply env
    var overrides. Missing file is not an error -- defaults apply."""
    config_path = path or Path("config.yaml")
    raw: dict = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        raw = loaded or {}

    data_dir = os.environ.get("FINPIPE_DATA_DIR") or raw.get("data_dir") or DEFAULT_DATA_DIR
    sheet_id = os.environ.get("FINPIPE_GOOGLE_SHEET_ID") or raw.get("google_sheet_id")
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or raw.get("google_credentials_path")
    worksheet_mapping = _parse_worksheet_mapping(raw)

    return FinPipeConfig(
        data_dir=Path(data_dir),
        google_sheet_id=sheet_id,
        google_credentials_path=Path(creds) if creds else None,
        google_sheets_worksheet_mapping=worksheet_mapping,
    )
