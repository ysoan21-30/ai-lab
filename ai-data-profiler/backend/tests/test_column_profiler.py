from app.profiling.column_profiler import profile_column


def test_numeric_profile_stats(clean_df):
    result = profile_column(clean_df["salary"], "salary", len(clean_df))
    assert result["dtype"] == "numeric"
    assert result["missing_count"] == 0
    assert "mean" in result and "median" in result and "std" in result
    assert result["min"] <= result["mean"] <= result["max"]


def test_categorical_profile_stats(clean_df):
    result = profile_column(clean_df["department"], "department", len(clean_df))
    assert result["dtype"] == "categorical"
    assert result["cardinality"] == 3
    assert len(result["top_values"]) <= 10


def test_missing_values_detected(messy_df):
    result = profile_column(messy_df["age"], "age", len(messy_df))
    assert result["missing_count"] > 0
    assert result["missing_percentage"] > 0


def test_constant_column_flagged(messy_df):
    result = profile_column(messy_df["constant_col"], "constant_col", len(messy_df))
    assert result["is_constant"] is True


def test_id_column_detected(clean_df):
    result = profile_column(clean_df["id"], "id", len(clean_df))
    assert result["looks_like_id"] is True


def test_negative_values_counted(messy_df):
    result = profile_column(messy_df["age"], "age", len(messy_df))
    assert result["negative_count"] >= 1


def test_balanced_binary_column_not_flagged_near_constant():
    import pandas as pd
    import numpy as np
    np.random.seed(0)
    n = 1000
    series = pd.Series(np.random.choice([0, 1], n, p=[0.5, 0.5]))
    result = profile_column(series, "churned", n)
    assert result["unique_count"] == 2
    assert result["is_near_constant"] is False


def test_dominant_value_column_flagged_near_constant():
    import pandas as pd
    n = 1000
    series = pd.Series([0] * 995 + [1] * 5)
    result = profile_column(series, "rare_flag", n)
    assert result["is_near_constant"] is True
