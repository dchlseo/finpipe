"""Google Sheets exporter, using `gspread` + a service-account credential.

Generic by design: a dataset type maps to a worksheet title, the worksheet
is cleared and rewritten with the normalized DataFrame. There is no
instrument-specific worksheet layout. Default titles live in
`_WORKSHEET_TITLES` below; `config.google_sheets_worksheet_mapping` (from
`google_sheets.worksheet_mapping` in config.yaml) overrides them per dataset
type, leaving unlisted types on their default. Any failure here (missing
config, missing credentials file, network/API failure) raises `ExportError`
with a plain-English message -- callers are expected to treat it as
non-fatal to the local save, which always happens first.
"""

from __future__ import annotations

from typing import Optional

import gspread
import pandas as pd

from finpipe.core.config import FinPipeConfig
from finpipe.core.exceptions import ExportError
from finpipe.core.models import DatasetType, InstrumentMetadata

_WORKSHEET_TITLES: dict[DatasetType, str] = {
    DatasetType.PRICE: "Price",
    DatasetType.DIVIDENDS: "Dividends",
    DatasetType.INCOME_STATEMENT: "Income Statement",
    DatasetType.INCOME_STATEMENT_QUARTERLY: "Income Statement (Quarterly)",
    DatasetType.BALANCE_SHEET: "Balance Sheet",
    DatasetType.BALANCE_SHEET_QUARTERLY: "Balance Sheet (Quarterly)",
    DatasetType.CASHFLOW: "Cash Flow",
    DatasetType.CASHFLOW_QUARTERLY: "Cash Flow (Quarterly)",
    DatasetType.FUNDAMENTALS: "Fundamentals",
    DatasetType.MACRO_SERIES: "Macro Series",
}


def _frame_to_values(frame: pd.DataFrame) -> list[list]:
    df = frame.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    df = df.astype(object).where(pd.notnull(df), "")
    return [list(map(str, df.columns))] + df.values.tolist()


def _metadata_values(meta: InstrumentMetadata) -> list[list]:
    return [["field", "value"]] + [[k, "" if v is None else str(v)] for k, v in meta.to_dict().items()]


class GoogleSheetsExporter:
    def __init__(self, config: FinPipeConfig):
        self.config = config
        # Custom worksheet titles from config only override the dataset
        # types they name; everything else keeps its built-in default.
        self._worksheet_titles: dict[DatasetType, str] = {
            **_WORKSHEET_TITLES,
            **config.google_sheets_worksheet_mapping,
        }

    def export(
        self, meta: InstrumentMetadata, datasets: dict[DatasetType, Optional[pd.DataFrame]]
    ) -> None:
        if not self.config.google_sheet_id:
            raise ExportError(
                "No Google Sheet ID configured (set google_sheet_id in config.yaml "
                "or the FINPIPE_GOOGLE_SHEET_ID env var)."
            )
        if not self.config.google_credentials_path:
            raise ExportError(
                "No Google service-account credentials configured (set "
                "google_credentials_path in config.yaml or GOOGLE_APPLICATION_CREDENTIALS)."
            )
        if not self.config.google_credentials_path.exists():
            raise ExportError(f"Credentials file not found: {self.config.google_credentials_path}")

        try:
            client = gspread.service_account(filename=str(self.config.google_credentials_path))
            spreadsheet = client.open_by_key(self.config.google_sheet_id)
        except Exception as exc:
            raise ExportError(f"Could not connect to Google Sheets: {exc}") from exc

        self._write_worksheet(spreadsheet, "Metadata", _metadata_values(meta))
        for dataset_type, frame in datasets.items():
            if frame is None or frame.empty:
                continue
            title = self._worksheet_titles.get(dataset_type)
            if title is None:
                continue
            self._write_worksheet(spreadsheet, title, _frame_to_values(frame))

    def _write_worksheet(self, spreadsheet, title: str, values: list[list]) -> None:
        try:
            try:
                worksheet = spreadsheet.worksheet(title)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=title, rows=max(len(values) + 1, 10), cols=max(len(values[0]), 5)
                )
            worksheet.clear()
            worksheet.update(values)
        except ExportError:
            raise
        except Exception as exc:
            raise ExportError(f"Failed writing '{title}' worksheet: {exc}") from exc
