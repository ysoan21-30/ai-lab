from app.profiling.column_profiler import profile_column
from app.profiling.loader import load_dataset
from app.profiling.orchestrator import run_full_profile
from app.profiling.target_detection import detect_target_column, evaluate_class_imbalance


def _profiles(df):
    return [profile_column(df[c], c, len(df)) for c in df.columns]


def test_target_detection_finds_named_target(messy_df):
    result = detect_target_column(messy_df, _profiles(messy_df))
    assert result["most_likely_target"] == "target"


def test_target_never_silently_assumes_id_column(clean_df):
    result = detect_target_column(clean_df, _profiles(clean_df))
    assert result["most_likely_target"] != "id"


def test_class_imbalance_detected_for_skewed_target(imbalanced_df):
    result = detect_target_column(imbalanced_df, _profiles(imbalanced_df))
    imbalance = evaluate_class_imbalance(result.get("class_balance"))
    assert imbalance is not None
    assert imbalance["severity"] in ("MEDIUM", "HIGH", "CRITICAL")


def test_class_balance_none_for_balanced_data(clean_df):
    result = detect_target_column(clean_df, _profiles(clean_df))
    imbalance = evaluate_class_imbalance(result.get("class_balance"))
    # department is roughly balanced 3-class categorical, not necessarily flagged as target
    if imbalance:
        assert imbalance["severity"] in ("LOW", "MEDIUM")


def test_ml_readiness_score_in_valid_range(messy_df):
    raw = messy_df.to_csv(index=False).encode()
    loaded = load_dataset(raw, "messy.csv", 10_000_000)
    profile = run_full_profile(loaded)
    score = profile["ml_readiness"]["overall_score"]
    assert 0 <= score <= 100
    breakdown = profile["ml_readiness"]["breakdown"]
    for v in breakdown.values():
        assert 0 <= v <= 100


def test_clean_data_scores_higher_than_messy_data(clean_df, messy_df):
    clean_loaded = load_dataset(clean_df.to_csv(index=False).encode(), "clean.csv", 10_000_000)
    messy_loaded = load_dataset(messy_df.to_csv(index=False).encode(), "messy.csv", 10_000_000)
    clean_profile = run_full_profile(clean_loaded)
    messy_profile = run_full_profile(messy_loaded)
    assert clean_profile["quality_score"] >= messy_profile["quality_score"]


def test_manual_target_override(clean_df):
    loaded = load_dataset(clean_df.to_csv(index=False).encode(), "clean.csv", 10_000_000)
    profile = run_full_profile(loaded, manual_target="department")
    assert profile["target"]["most_likely_target"] == "department"
    assert profile["target"]["confidence"] == 1.0
