"""User-readable exceptions used across FinPipe.

These are the "expected failure" cases described in the README/architecture
docs. They are caught at the CLI boundary and printed as plain messages
rather than tracebacks. Anything else that escapes is a genuine bug.
"""


class FinPipeError(Exception):
    """Base class for all expected FinPipe errors."""


class UnsupportedInstrument(FinPipeError):
    """Raised when a symbol resolves to a source that isn't implemented."""


class DatasetUnavailable(FinPipeError):
    """Raised by a source adapter when a dataset genuinely has no data."""


class SourceError(FinPipeError):
    """Raised when a source adapter fails to fetch required data (e.g. an
    invalid ticker, or an upstream API failure fetching metadata)."""


class ExportError(FinPipeError):
    """Raised when the Google Sheets export cannot complete."""


class ConfigError(FinPipeError):
    """Raised when config.yaml contains an invalid or unrecognized value."""
