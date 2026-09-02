"""Configuration loading.

FinPipe works with zero configuration (local save just uses `./data`).
`config.yaml` (gitignored; copy from `config.example.yaml`) and environment
variables are both optional, additive ways to set the Google Sheets
destination and override the local data directory. Env vars win over the
config file so credentials never need to live in a committed file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_DATA_DIR = "data"


@dataclass
class FinPipeConfig:
    data_dir: Path
    google_sheet_id: Optional[str] = None
    google_credentials_path: Optional[Path] = None


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

    return FinPipeConfig(
        data_dir=Path(data_dir),
        google_sheet_id=sheet_id,
        google_credentials_path=Path(creds) if creds else None,
    )
