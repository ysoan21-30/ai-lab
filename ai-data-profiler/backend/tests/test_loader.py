import pandas as pd
import pytest

from app.profiling.loader import DatasetLoadError, load_dataset


def test_loads_valid_csv(clean_df):
    raw = clean_df.to_csv(index=False).encode()
    loaded = load_dataset(raw, "data.csv", 10_000_000)
    assert loaded.df.shape[0] == clean_df.shape[0]
    assert loaded.detected_format == "csv"


def test_rejects_empty_file():
    with pytest.raises(DatasetLoadError):
        load_dataset(b"", "data.csv", 10_000_000)


def test_rejects_oversized_file(clean_df):
    raw = clean_df.to_csv(index=False).encode()
    with pytest.raises(DatasetLoadError):
        load_dataset(raw, "data.csv", 10)  # 10 bytes max


def test_rejects_headers_only():
    with pytest.raises(DatasetLoadError):
        load_dataset(b"a,b,c\n", "data.csv", 10_000_000)


def test_rejects_corrupted_xlsx_extension():
    with pytest.raises(DatasetLoadError):
        load_dataset(b"this is not an excel file", "data.xlsx", 10_000_000)


def test_dedupes_duplicate_column_names():
    raw = b"a,a,b\n1,2,3\n4,5,6\n"
    loaded = load_dataset(raw, "dupes.csv", 10_000_000)
    assert list(loaded.df.columns) == ["a", "a.1", "b"]


def test_handles_mixed_encoding_gracefully():
    raw = "col1,col2\ncafé,1\nnaïve,2\n".encode("latin-1")
    loaded = load_dataset(raw, "encoded.csv", 10_000_000)
    assert loaded.df.shape[0] == 2
