"""Regression tests for correlation-based leakage detection against
boolean/0-1-coded targets -- the most common binary classification target
format. These previously failed silently because the correlation matrix
excluded any column classified as dtype "boolean", which meant a 0/1 target
was never present in the Pearson matrix leakage.py inspects.
"""
import numpy as np
import pandas as pd

from app.profiling.loader import load_dataset
from app.profiling.orchestrator import run_full_profile


def test_boolean_target_included_in_correlation_matrix():
    np.random.seed(0)
    n = 400
    target = np.random.choice([0, 1], n, p=[0.6, 0.4])
    df = pd.DataFrame({
        "id": range(n),
        "age": np.random.randint(18, 70, n),
        "target": target,
    })
    loaded = load_dataset(df.to_csv(index=False).encode(), "t.csv", 10_000_000)
    profile = run_full_profile(loaded)
    assert "target" in profile["correlation"]["pearson"], (
        "Boolean-coded target column must appear in the correlation matrix "
        "for leakage detection to be able to inspect it."
    )


def test_leakage_detected_via_near_perfect_correlation_with_boolean_target():
    np.random.seed(1)
    n = 400
    target = np.random.choice([0, 1], n, p=[0.6, 0.4])
    df = pd.DataFrame({
        "id": range(n),
        "leaky_feature": target.astype(float) + np.random.normal(0, 0.001, n),
        "age": np.random.randint(18, 70, n),
        "target": target,
    })
    loaded = load_dataset(df.to_csv(index=False).encode(), "leak.csv", 10_000_000)
    profile = run_full_profile(loaded)
    assert profile["target"]["most_likely_target"] == "target"
    leaked_columns = {w["column"] for w in profile["leakage_warnings"]}
    assert "leaky_feature" in leaked_columns
    # Leakage risk component of ML readiness must be penalized below the default 100.
    assert profile["ml_readiness"]["breakdown"]["leakage_risk"] < 100


def test_no_leakage_warning_for_unrelated_boolean_target():
    np.random.seed(2)
    n = 400
    df = pd.DataFrame({
        "id": range(n),
        "unrelated_feature": np.random.normal(0, 1, n),
        "target": np.random.choice([0, 1], n, p=[0.6, 0.4]),
    })
    loaded = load_dataset(df.to_csv(index=False).encode(), "clean.csv", 10_000_000)
    profile = run_full_profile(loaded)
    assert profile["leakage_warnings"] == []
    assert profile["ml_readiness"]["breakdown"]["leakage_risk"] == 100
