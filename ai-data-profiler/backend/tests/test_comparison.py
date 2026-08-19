"""Tests for dataset comparison service."""
import numpy as np
import pandas as pd

from app.services.comparison import compare_datasets


def _make_df_a():
    np.random.seed(10)
    return pd.DataFrame({
        "id": range(100),
        "age": np.random.randint(18, 65, 100),
        "salary": np.random.normal(60000, 10000, 100),
        "department": np.random.choice(["Eng", "Sales"], 100),
    })


def _make_df_b():
    """Variant of A: more rows, one column dropped, one added, salary shifted up."""
    np.random.seed(20)
    n = 150
    return pd.DataFrame({
        "id": range(n),
        "age": np.random.randint(20, 70, n),
        "salary": np.random.normal(75000, 12000, n),  # shifted up
        "region": np.random.choice(["US", "EU", "APAC"], n),  # new column
        # department dropped
    })


def test_schema_diff_detects_additions_and_removals():
    result = compare_datasets(_make_df_a(), _make_df_b())
    assert "department" in result["schema_diff"]["columns_only_in_a"]
    assert "region" in result["schema_diff"]["columns_only_in_b"]
    assert "id" in result["schema_diff"]["common_columns"]


def test_shape_comparison():
    result = compare_datasets(_make_df_a(), _make_df_b())
    assert result["shape"]["rows_a"] == 100
    assert result["shape"]["rows_b"] == 150
    assert result["shape"]["row_diff"] == 50


def test_distribution_shift_detected_for_salary():
    """Salary mean shifted from ~60K to ~75K -- should trigger a shift warning."""
    result = compare_datasets(_make_df_a(), _make_df_b())
    shifts = {s["column"]: s for s in result["distribution_shifts"]}
    assert "salary" in shifts
    assert shifts["salary"]["cohens_d"] > 0.5  # substantial shift


def test_quality_delta_computed():
    result = compare_datasets(_make_df_a(), _make_df_b())
    qd = result["quality_delta"]
    assert "issues_a" in qd
    assert "issues_b" in qd
    assert "issues_delta" in qd


def test_identical_datasets_show_no_shifts():
    df = _make_df_a()
    result = compare_datasets(df, df.copy())
    assert len(result["distribution_shifts"]) == 0
    assert result["shape"]["row_diff"] == 0


def test_column_diffs_include_missing_pct():
    df_a = _make_df_a()
    df_b = _make_df_a().copy()
    df_b.loc[:19, "age"] = np.nan  # introduce 20% missing
    result = compare_datasets(df_a, df_b)
    age_diff = next(d for d in result["column_diffs"] if d["column"] == "age")
    assert age_diff["missing_pct_b"] > age_diff["missing_pct_a"]
