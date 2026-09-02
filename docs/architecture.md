# FinPipe architecture

This document explains the *why* behind FinPipe's structure, in more
technical detail than the README. It assumes you've read the README first.

## The pipeline

```
CLI (finpipe/cli.py)
  -> core.resolver.resolve(symbol)      picks a SourceAdapter
  -> SourceAdapter.fetch_*()             source-specific, returns normalized data
  -> core.pipeline.run_fetch()           loops dataset types, collects outcomes
  -> storage.local.LocalStorage          always: JSON + CSV on disk
  -> exporters.google_sheets (optional)  only with --sheets
  -> cli renders the summary
```

Every arrow above is a real module boundary, not just a mental model. The
CLI never imports `yfinance`; the storage layer never imports `gspread`;
the exporter never imports `yfinance`. Each module only knows about the
shared types in `core/models.py` (`InstrumentMetadata`, `NormalizedDataset`,
`DatasetType`) plus whatever comes immediately before it in the pipeline.

## Why source adapters exist

Every financial data provider has its own SDK, its own dataframe shapes,
its own quirks (`yfinance`'s statements are periods-as-columns; a REST API
might paginate; a macro data source might return a single flat series).
If that provider-specific shape leaked into the CLI, storage, or exporter,
every one of those modules would need a special case per source, and
replacing a source would mean touching the whole codebase.

Instead, `sources/base.py` defines a small, fixed contract
(`SourceAdapter`): `fetch_metadata()` plus one `fetch_*()` method per
`DatasetType`, each returning either a normalized `pandas.DataFrame`,
`None` (no data for this symbol), or raising a documented exception. A
source adapter is the *only* place allowed to import that provider's SDK.
`sources/yahoo.py` is the concrete (and, in the MVP, only) example.

## Why normalization is a separate layer

Normalization -- turning "whatever yfinance's `.history()` returned" into
"a DataFrame with a `date` column, snake_case columns, sorted ascending" --
happens *inside* the source adapter, as free functions (`normalize_price_history`,
`normalize_dividends`, `normalize_statement` in `sources/yahoo.py`) rather
than being scattered through the pipeline or CLI. This keeps the
transformation testable in isolation (see `tests/test_normalization.py`,
which never imports `yfinance`) and keeps the boundary explicit: anything
past `SourceAdapter.fetch_*()` is normalized data, full stop.

The MVP's normalization is intentionally light: statements keep Yahoo's own
line-item vocabulary (snake_cased, not remapped to a chart of accounts),
because building a universal accounting ontology across US GAAP, Japanese
and Korean standards, etc. is a real project on its own -- not something to
bolt on as a side effect of an ingestion MVP.

## Why asset classes don't share a fake uniform schema

`InstrumentMetadata` has optional fields (`exchange`, `currency`, `country`)
precisely because a crypto pair has no exchange or country, and a future
macro series would have none of the identity fields at all. Rather than
force every asset into an equity-shaped schema and paper over the gaps with
placeholder values, missing fields are simply `None`, and missing datasets
are simply not fetched or saved (`SourceAdapter.SUPPORTED_DATASETS` says
what a source *can* produce; a fetch returning `None` says a given symbol
*doesn't have* that dataset). Both cases are reported to the user as
plain, informational lines -- never as errors, never as empty files on
disk. See the table in the README for how this plays out across the four
MVP symbols.

## How to add a new source

1. Create `finpipe/sources/<name>.py` with a class implementing
   `SourceAdapter`: set `name`, set `SUPPORTED_DATASETS` to whatever
   dataset types this source can actually produce, and implement the
   corresponding `fetch_*()` methods. Put all of that source's SDK/HTTP
   specifics here, and normalize before returning.
2. Register it in `finpipe/core/resolver.py`'s `_REGISTRY` dict, keyed by
   the prefix users will type (e.g. `"fred"` for `FRED:CPIAUCSL`).
3. Nothing else changes. `core/pipeline.py`, `storage/local.py`,
   `exporters/google_sheets.py`, and `cli.py` are all already generic over
   `SourceAdapter`.

### Hypothetical example: `FredSource`

This is illustrative only -- **not implemented** in the MVP.

```python
# finpipe/sources/fred.py
class FredSource(SourceAdapter):
    name = "fred"
    SUPPORTED_DATASETS = {DatasetType.METADATA, DatasetType.MACRO_SERIES}

    def fetch_metadata(self, series_id: str) -> InstrumentMetadata:
        # call the FRED API, map its series description into
        # InstrumentMetadata(asset_type="macro", exchange=None,
        # currency=None, country=None, source="fred")
        ...

    def fetch_macro_series(self, series_id: str) -> pd.DataFrame:
        # call the FRED API, normalize into columns: date, value
        ...
```

```python
# finpipe/core/resolver.py
_REGISTRY = {
    "yahoo": YahooSource(),
    "fred": FredSource(),
}
```

With that in place, `finpipe fetch FRED:CPIAUCSL` resolves, fetches
metadata + a macro series, and is saved to
`data/macro/FRED_CPIAUCSL/` -- using the exact same pipeline, storage, and
CLI code already in place for equities and crypto.

## How to add a new dataset type

1. Add the new value to `DatasetType` in `core/models.py`.
2. Add a `fetch_<name>()` method to `SourceAdapter` in `sources/base.py`,
   and an entry in `DATASET_FETCH_METHODS` mapping the type to that method
   name -- this is what `core/pipeline.py` iterates over.
3. Implement the method on whichever source adapters actually support it
   (and add the type to their `SUPPORTED_DATASETS`); adapters that don't
   support it need no change -- the pipeline already treats an unlisted
   type as "not supported by source".

## How future analytics should fit in

`finpipe/analytics/` is an empty placeholder in the MVP on purpose. When
analytics are added, they should be plain functions that take normalized
`InstrumentMetadata`/`NormalizedDataset` objects (or the equivalent saved
CSV/JSON files) as input -- never a source-specific object. That keeps
analytics uniform across sources: a valuation function written against
Yahoo-sourced equity data should keep working unmodified if a second
equity source is added later, because both would have gone through the
same normalization boundary.
