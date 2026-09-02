from finpipe.core.models import DatasetType, FetchOutcome, InstrumentMetadata


def test_instrument_metadata_optional_fields_default_to_none():
    meta = InstrumentMetadata(symbol="BTC-USD", name="Bitcoin USD", asset_type="crypto", source="yahoo")
    assert meta.exchange is None
    assert meta.currency is None
    assert meta.country is None


def test_instrument_metadata_roundtrip_dict():
    meta = InstrumentMetadata(
        symbol="6758.T",
        name="Sony Group Corporation",
        asset_type="equity",
        source="yahoo",
        exchange="TSE",
        currency="JPY",
        country="JP",
    )
    restored = InstrumentMetadata.from_dict(meta.to_dict())
    assert restored == meta


def test_dataset_type_values_are_strings():
    assert DatasetType.PRICE == "price"
    assert DatasetType.INCOME_STATEMENT.value == "income_statement"


def test_fetch_outcome_defaults_detail_to_none():
    outcome = FetchOutcome(DatasetType.DIVIDENDS, "not_supported")
    assert outcome.detail is None
