"""Optional export destinations for normalized datasets (e.g. Google Sheets).

Exporters are intentionally decoupled from source/storage code -- they only
ever consume `InstrumentMetadata` + `NormalizedDataset`s, the same boundary
storage uses.
"""
