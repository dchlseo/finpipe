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
from gspread.utils import ValueInputOption

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


def _frame_to_values(frame: pd.DataFrame) -> tuple[list[list], list[int]]:
    """Flatten a DataFrame into a values grid for `gspread`, plus the
    0-based column indices that hold dates.

    Datetime columns are stringified to ISO ``YYYY-MM-DD`` so the grid stays
    JSON-serializable; the returned indices let the caller re-write just
    those columns with `USER_ENTERED` semantics so Sheets stores them as
    real date values instead of text (see `_write_worksheet`).
    """
    df = frame.copy()
    date_col_indices = []
    for i, col in enumerate(df.columns):
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
            date_col_indices.append(i)
    df = df.astype(object).where(pd.notnull(df), "")
    values = [list(map(str, df.columns))] + df.values.tolist()
    return values, date_col_indices


def _col_letter(index: int) -> str:
    """0-based column index -> spreadsheet column letter (0 -> 'A', 25 -> 'Z', 26 -> 'AA', ...)."""
    letters = ""
    n = index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


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
            values, date_col_indices = _frame_to_values(frame)
            self._write_worksheet(spreadsheet, title, values, date_col_indices)

    def _write_worksheet(
        self,
        spreadsheet,
        title: str,
        values: list[list],
        date_col_indices: Optional[list[int]] = None,
    ) -> None:
        try:
            try:
                worksheet = spreadsheet.worksheet(title)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=title, rows=max(len(values) + 1, 10), cols=max(len(values[0]), 5)
                )
            worksheet.clear()
            worksheet.update(values)
            for col in date_col_indices or []:
                self._write_date_column(worksheet, values, col)
        except ExportError:
            raise
        except Exception as exc:
            raise ExportError(f"Failed writing '{title}' worksheet: {exc}") from exc

    def _write_date_column(self, worksheet, values: list[list], col: int) -> None:
        """Re-write one already-written column with `USER_ENTERED` input so
        Sheets stores its ISO date strings as real date values (recognized
        by `MAX`, `XLOOKUP`, `YEAR`, `EDATE`, etc.) instead of plain text,
        then pin its display format so it still reads as `YYYY-MM-DD`
        regardless of the spreadsheet's locale.

        Scoped to a single known-datetime column so no other column's
        values -- numeric or text -- are ever re-parsed by Sheets.
        """
        if len(values) < 2:
            return  # header only, nothing to re-parse as a date
        letter = _col_letter(col)
        cell_range = f"{letter}2:{letter}{len(values)}"
        column_values = [[row[col]] for row in values[1:]]
        worksheet.update(column_values, cell_range, value_input_option=ValueInputOption.user_entered)
        worksheet.format(cell_range, {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}})
