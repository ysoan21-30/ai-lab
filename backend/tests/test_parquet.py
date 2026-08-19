"""Tests for Parquet file loading support."""
import io

import numpy as np
import pandas as pd
import pytest

from app.profiling.loader import DatasetLoadError, load_dataset


def _make_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


@pytest.fixture
def sample_df():
    np.random.seed(42)
    return pd.DataFrame({
        "id": range(50),
        "value": np.random.normal(0, 1, 50),
        "category": np.random.choice(["a", "b", "c"], 50),
    })


def test_load_parquet_file(sample_df):
    raw = _make_parquet_bytes(sample_df)
    result = load_dataset(raw, "test.parquet", 50_000_000)
    assert result.detected_format == "parquet"
    assert result.df.shape == sample_df.shape
    assert list(result.df.columns) == list(sample_df.columns)


def test_parquet_magic_bytes_detected_regardless_of_extension(sample_df):
    """Parquet files are identified by magic bytes, not extension."""
    raw = _make_parquet_bytes(sample_df)
    result = load_dataset(raw, "data.csv", 50_000_000)
    assert result.detected_format == "parquet"


def test_parquet_extension_with_wrong_content_rejected():
    """A .parquet extension with non-parquet content should be rejected."""
    raw = b"this is just plain text, not parquet"
    with pytest.raises(DatasetLoadError, match="parquet"):
        load_dataset(raw, "fake.parquet", 50_000_000)


def test_parquet_preserves_dtypes(sample_df):
    """Parquet preserves column types better than CSV."""
    raw = _make_parquet_bytes(sample_df)
    result = load_dataset(raw, "typed.parquet", 50_000_000)
    assert result.df["id"].dtype in (np.int64, np.int32)
    assert result.df["value"].dtype == np.float64
