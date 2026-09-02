# FinPipe

FinPipe is a small command-line tool that fetches financial and economic
data for an instrument, normalizes it into a consistent structure, and
saves it locally -- with an optional export to Google Sheets. It's a data
*ingestion* tool, not an analysis tool: it gets you clean, repeatable local
datasets to build on.

```
finpipe fetch 6758.T
finpipe fetch GOOGL
finpipe fetch 005930.KS
finpipe fetch BTC-USD
```

## Why it exists

Pulling financial data by hand -- from Google Finance, a broker site, or an
API's own quirky response shape -- is inconsistent and not repeatable.
FinPipe exists to:

- separate **retrieval** (getting raw data from a source) from
  **analysis** (what you do with it once it's normalized and saved),
- give repeatable, one-command data pulls you can rerun anytime,
- support more than equities from day one -- crypto, and eventually macro
  series, without forcing every asset class into the same schema,
- make adding a new data source (FRED, DART, EDINET, ...) a matter of
  writing one new adapter, not rewriting the app.

## Architecture

```
CLI
 -> Resolver          (picks a source adapter for the symbol)
 -> Source            (fetches from that provider's SDK/API)
 -> Normalization      (source-specific shapes -> consistent DataFrames)
 -> Local Storage      (JSON + CSV on disk)
 -> Optional Google Sheets export
```

| Module | Responsibility |
|---|---|
| `finpipe/cli.py` | Argument parsing and printing the run summary. No business logic. |
| `finpipe/core/` | Source-agnostic types (`InstrumentMetadata`, `DatasetType`, ...), the resolver, the pipeline orchestrator, and config loading. |
| `finpipe/sources/` | One module per data provider. `base.py` defines the contract; `yahoo.py` is the only implementation in the MVP, and the only place `yfinance` is imported. |
| `finpipe/storage/` | Saves normalized data locally as JSON (metadata) and CSV (tabular datasets). No database. |
| `finpipe/exporters/` | Optional export destinations. `google_sheets.py` is the only one, and is fully decoupled from the source/storage code. |
| `finpipe/analytics/` | Empty placeholder for future analysis modules. |

See [`docs/architecture.md`](docs/architecture.md) for the design
rationale in more depth, including how to add a new source or dataset
type.

## Installation

```bash
git clone <this-repo-url>
cd finpipe
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS/Linux
pip install -r requirements.txt
```

This gives you `python -m finpipe ...`. If you'd rather run `finpipe ...`
directly, install the package itself (in the same virtual environment):

```bash
pip install -e .
```

## Basic usage

```bash
finpipe fetch 6758.T          # Sony Group (Tokyo)
finpipe fetch GOOGL           # Alphabet
finpipe fetch 005930.KS       # Samsung Electronics (Korea)
finpipe fetch BTC-USD         # Bitcoin
```

A successful run prints a summary like:

```
Instrument: Sony Group Corporation
Symbol: 6758.T
Asset type: equity

Fetched:
✓ metadata
✓ price
✓ income statement
✓ balance sheet
✓ cash flow
✓ dividends
- fundamentals (not supported by source)
- macro series (not supported by source)

Saved:
data/equity/6758.T/
```

Datasets that don't apply to an instrument (e.g. financial statements for
`BTC-USD`) or aren't produced by the current source (e.g. `fundamentals`
and `macro_series` for Yahoo, in this MVP) are reported informationally --
never as a crash.

Add `--sheets` to also export the fetched data to a configured Google
Sheet (local save always happens regardless):

```bash
finpipe fetch GOOGL --sheets
```

`--local` is accepted for parity with the flag-based examples above but
has no additional effect -- local save is always on in the MVP; there's no
`--no-local`. `--config PATH` points at a config file other than the
default `./config.yaml`.

## Output

```
data/
    equity/
        6758.T/
            metadata.json
            price.csv
            income_statement.csv
            balance_sheet.csv
            cashflow.csv
            dividends.csv
        GOOGL/
            ...
        005930.KS/
            ...
    crypto/
        BTC-USD/
            metadata.json
            price.csv
```

No file is written for a dataset that isn't supported or has no data --
`data/crypto/BTC-USD/` really only contains those two files.

`metadata.json` looks like:

```json
{
  "symbol": "6758.T",
  "name": "Sony Group Corporation",
  "asset_type": "equity",
  "source": "yahoo",
  "exchange": "JPX",
  "currency": "JPY",
  "country": "Japan"
}
```

CSV files are readable directly with `pandas.read_csv(...)`, or any spreadsheet tool.

## Google Sheets setup

Google Sheets export is entirely optional -- everything above works
without it.

1. In the [Google Cloud Console](https://console.cloud.google.com/),
   create (or reuse) a project and enable the **Google Sheets API**.
2. Create a **service account**, then create and download a JSON key for
   it.
3. Open the target Google Sheet and **share it** with the service
   account's email address (found in the JSON key file, looks like
   `...@...iam.gserviceaccount.com`) as an **Editor**.
4. Copy [`config.example.yaml`](config.example.yaml) to `config.yaml` and
   fill in `google_sheet_id` (from the sheet's URL) and
   `google_credentials_path` (path to the JSON key) -- or set the
   equivalent environment variables from
   [`.env.example`](.env.example) (`FINPIPE_GOOGLE_SHEET_ID`,
   `GOOGLE_APPLICATION_CREDENTIALS`). Environment variables take
   precedence over `config.yaml`.
5. Run `finpipe fetch <SYMBOL> --sheets`. Each dataset type is written to
   its own worksheet (`Metadata`, `Price`, `Income Statement`, `Balance
   Sheet`, `Cash Flow`, `Dividends`), created if missing and overwritten
   on every run. Worksheet structure is generic -- there's no
   instrument-specific layout.

Never commit `config.yaml` or your credentials JSON file -- both are
gitignored by default.

## Supported sources

- **Yahoo Finance** (via [`yfinance`](https://pypi.org/project/yfinance/))
  -- the only source implemented in this MVP.

Nothing else (FRED, DART, EDINET, etc.) is implemented yet, even though
the architecture is built to add them without rewrites -- see
[`docs/architecture.md`](docs/architecture.md). Using a `SOURCE:CODE`
symbol for an unregistered source (e.g. `FRED:CPIAUCSL`) fails with a
clear "not implemented yet" message rather than pretending to work.

## Supported asset classes

| Asset class | Status |
|---|---|
| Equity (`6758.T`, `GOOGL`, `005930.KS`) | Tested |
| Crypto (`BTC-USD`) | Tested |
| ETF / index | Theoretically extensible (same Yahoo `quoteType` mapping), not manually tested |
| Macro series (e.g. `FRED:CPIAUCSL`) | Planned -- architecture supports it, no source implements it yet |

Per-asset dataset coverage observed during manual testing:

| Asset | Price | Statements | Dividends | Macro |
|---|---|---|---|---|
| Sony (`6758.T`) | yes | yes | yes | n/a |
| Alphabet (`GOOGL`) | yes | yes | yes | n/a |
| Samsung (`005930.KS`) | yes | yes | yes | n/a |
| Bitcoin (`BTC-USD`) | yes | no | no | n/a |

## Limitations

- `yfinance` is an unofficial wrapper around Yahoo endpoints, not an
  official API -- it can be rate-limited, change shape, or fail without
  notice. It also logs its own diagnostics (e.g. HTTP error lines) to
  stderr on some failures; that's `yfinance`'s own logging, separate from
  FinPipe's own `Error: ...` message.
- International fundamentals (Sony, Samsung) may be incomplete or use
  different accounting-standard line items than a US filer; FinPipe
  preserves Yahoo's own labels rather than reconciling accounting
  standards.
- Crypto has no company fundamentals by design -- statements and
  dividends will consistently show "no data available" for `BTC-USD`,
  which is expected, not a bug.
- Fields can be missing or `null` depending on what Yahoo returns for a
  given symbol (e.g. `country` for some tickers).
- No historical diffing or append logic -- each `fetch` overwrites that
  symbol's local files; prior data-provider restatements aren't
  preserved.
- No rate-limiting or retry/backoff around Yahoo calls.
- Price history frequency is whatever `yfinance`'s default `history()`
  call returns (daily); there's no `--interval` option in the MVP.

## Future roadmap

Not implemented, but the architecture is built to accommodate:

- Additional sources: FRED, DART, EDINET, other market-data APIs.
- Analytics modules (`finpipe/analytics/`) built on top of normalized data.
- Google Sheets templates/formatting beyond a plain data dump.
- Scheduled/automated updates.

## Testing

```bash
pytest
```

Tests are offline -- external calls (`yfinance`, `gspread`) are mocked or
avoided entirely. They cover instrument/dataset models, symbol resolution,
Yahoo normalization rules, the `SourceAdapter` contract, and local
save/load roundtrips. Manual testing against live Yahoo Finance data was
also performed for all four MVP symbols (`6758.T`, `GOOGL`, `005930.KS`,
`BTC-USD`); see Limitations above for what that testing surfaced.
