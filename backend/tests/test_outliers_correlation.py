import numpy as np
import pandas as pd

from app.profiling.column_profiler import profile_column
from app.profiling.correlation import analyze_correlations
from app.profiling.outliers import detect_outliers


def _profiles(df):
    return [profile_column(df[c], c, len(df)) for c in df.columns]


def test_outlier_detection_finds_injected_outliers():
    np.random.seed(0)
    values = np.random.normal(50, 5, 200)
    values[0:5] = [500, -500, 480, 490, -450]  # obvious outliers
    df = pd.DataFrame({"x": values})
    results = detect_outliers(df, _profiles(df))
    assert any(r["column"] == "x" and r["count"] >= 4 for r in results)


def test_no_outliers_on_uniform_data():
    df = pd.DataFrame({"x": [5.0] * 50})
    results = detect_outliers(df, _profiles(df))
    assert results == [] or all(r["count"] == 0 for r in results)


def test_correlation_detects_highly_correlated_pair():
    np.random.seed(0)
    x = np.random.normal(0, 1, 300)
    df = pd.DataFrame({"x": x, "y": x * 2 + 0.001, "z": np.random.normal(0, 1, 300)})
    result = analyze_correlations(df, _profiles(df))
    pairs = {(p["column_a"], p["column_b"]) for p in result["high_correlation_pairs"]}
    assert ("x", "y") in pairs or ("y", "x") in pairs


def test_correlation_threshold_is_configurable():
    np.random.seed(0)
    x = np.random.normal(0, 1, 300)
    y = x * 0.7 + np.random.normal(0, 0.5, 300)
    df = pd.DataFrame({"x": x, "y": y})
    result_strict = analyze_correlations(df, _profiles(df), threshold=0.99)
    result_loose = analyze_correlations(df, _profiles(df), threshold=0.3)
    assert len(result_strict["high_correlation_pairs"]) <= len(result_loose["high_correlation_pairs"])
