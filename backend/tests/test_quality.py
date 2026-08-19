from app.profiling.column_profiler import profile_column
from app.profiling.quality import detect_quality_issues, missing_severity


def _profiles(df):
    return [profile_column(df[c], c, len(df)) for c in df.columns]


def test_missing_severity_buckets():
    assert missing_severity(0) == "NONE"
    assert missing_severity(3) == "LOW"
    assert missing_severity(10) == "MEDIUM"
    assert missing_severity(30) == "HIGH"
    assert missing_severity(60) == "CRITICAL"


def test_detects_missing_values(messy_df):
    result = detect_quality_issues(messy_df, _profiles(messy_df))
    types = {i["type"] for i in result["issues"]}
    assert "missing_values" in types


def test_detects_duplicate_rows(messy_df):
    result = detect_quality_issues(messy_df, _profiles(messy_df))
    assert result["exact_duplicate_rows"] > 0


def test_detects_constant_column(messy_df):
    result = detect_quality_issues(messy_df, _profiles(messy_df))
    types = {i["type"] for i in result["issues"]}
    assert "constant_column" in types


def test_detects_inconsistent_categoricals(messy_df):
    result = detect_quality_issues(messy_df, _profiles(messy_df))
    types = {i["type"] for i in result["issues"]}
    assert "inconsistent_categorical_values" in types


def test_no_false_positives_on_clean_data(clean_df):
    result = detect_quality_issues(clean_df, _profiles(clean_df))
    types = {i["type"] for i in result["issues"]}
    assert "missing_values" not in types
    assert "constant_column" not in types
    assert result["exact_duplicate_rows"] == 0


def test_high_cardinality_detected(high_cardinality_df):
    result = detect_quality_issues(high_cardinality_df, _profiles(high_cardinality_df))
    types = {i["type"] for i in result["issues"]}
    assert "potential_id_column" in types
