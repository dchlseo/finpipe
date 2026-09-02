import json

import pandas as pd

from finpipe.core.models import DatasetType, InstrumentMetadata
from finpipe.storage.local import LocalStorage


def _make_meta(**overrides):
    defaults = dict(symbol="BTC-USD", name="Bitcoin USD", asset_type="crypto", source="yahoo")
    defaults.update(overrides)
    return InstrumentMetadata(**defaults)


def test_save_metadata_writes_readable_json(tmp_path):
    storage = LocalStorage(tmp_path)
    meta = _make_meta()

    path = storage.save_metadata(meta)

    assert path == tmp_path / "crypto" / "BTC-USD" / "metadata.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["symbol"] == "BTC-USD"
    assert loaded["asset_type"] == "crypto"


def test_save_dataset_writes_readable_csv(tmp_path):
    storage = LocalStorage(tmp_path)
    meta = _make_meta()
    frame = pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "close": [42.0]})

    path = storage.save_dataset(meta, DatasetType.PRICE, frame)

    assert path == tmp_path / "crypto" / "BTC-USD" / "price.csv"
    roundtrip = pd.read_csv(path)
    assert roundtrip["close"].iloc[0] == 42.0


def test_save_dataset_none_writes_nothing(tmp_path):
    storage = LocalStorage(tmp_path)
    meta = _make_meta()

    path = storage.save_dataset(meta, DatasetType.DIVIDENDS, None)

    assert path is None
    assert not (tmp_path / "crypto" / "BTC-USD" / "dividends.csv").exists()


def test_save_dataset_empty_frame_writes_nothing(tmp_path):
    storage = LocalStorage(tmp_path)
    meta = _make_meta()

    path = storage.save_dataset(meta, DatasetType.DIVIDENDS, pd.DataFrame())

    assert path is None
