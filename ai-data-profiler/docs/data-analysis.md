# Data Analysis Methodology

This document explains what the profiling engine computes and how to
interpret it. It's aimed at a technical reader who wants to trust — and
audit — the numbers behind the report.

## Dataset overview

Row/column counts, per-dtype column counts (numeric/categorical/
datetime/boolean), and in-memory size.

## Per-column statistics

- **All columns**: dtype (classified via `column_profiler.classify_dtype`,
  which also detects boolean-coded 0/1 numeric columns and datetime columns
  that were read as text), missing count/percentage, unique count/percentage,
  constant/near-constant flags, and an ID-column heuristic (name pattern
  match, e.g. `customer_id`, or >99% uniqueness).
- **Numeric**: min/max/mean/median/std, quartiles + p1/p5/p95/p99, mode,
  zero count, negative count, skewness and kurtosis (SciPy).
- **Categorical**: top 10 values with frequency, rare categories (≤1% of
  rows), cardinality, and a high-cardinality flag (>50 unique values and
  >50% of row count).
- **Datetime**: min/max date, missing dates, and a "suspicious range" flag
  for future dates or dates before 1900.

## Data quality issues

Each issue has a `type`, optional `column`, `severity`
(`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`), a human-readable `detail`, and a
concrete `recommendation` (often including a ready-to-run pandas snippet).

Missing-value severity thresholds: `<5%` LOW, `<20%` MEDIUM, `<50%` HIGH,
`≥50%` CRITICAL.

Detected issue types: `missing_values`, `duplicate_rows`,
`duplicate_id_candidates`, `constant_column`, `near_constant_column`,
`high_cardinality`, `potential_id_column`, `inconsistent_categorical_values`
(case/whitespace variants of the same category), `invalid_value` (e.g.
negative age/salary, out-of-range percentage), `suspicious_date_range`.

## Outlier detection

Two independent methods are run per numeric column and reported separately
(never combined into one number, since they can disagree):

- **IQR**: values outside `[Q1 − 1.5·IQR, Q3 + 1.5·IQR]`.
- **Z-score**: `|z| > 3`.

Outliers are always reported with a plain-language "potential impact" note
and a recommendation to review — the engine never deletes or transforms
data automatically.

## Correlation analysis

Pearson and Spearman correlation matrices over numeric columns. Pairs with
`|Pearson r| ≥ threshold` (default `0.90`, configurable per request) are
surfaced as "high correlation pairs" with an explanation of multicollinearity
and redundancy risk.

## Target detection

A weighted heuristic (`target_detection.py`) scores each column on: name
pattern match (e.g. `target`, `label`, `churn`, `is_*`), low cardinality for
categoricals (2–20 classes), being the last few columns in the dataset. ID
columns are always excluded. The highest-scoring column above a `0.4`
confidence threshold is surfaced as "most likely target" — always with the
disclaimer that this is heuristic, and the UI lets the user override it
manually (`POST /api/analyses/{id}/target`).

## Class imbalance

If a target is (auto- or manually-) selected and is categorical, class
proportions are computed and an imbalance ratio (majority/minority) is
classified: `<3` LOW, `<10` MEDIUM, `<20` HIGH, `≥20` CRITICAL, with a
recommendation toward resampling/class-weighting/stratified metrics.

## Potential data leakage

Deliberately conservative — the product never states leakage as fact. Two
signals: (1) a feature correlated with the likely target at `|r| ≥ 0.98`,
and (2) column names containing fragments like `result`, `outcome`,
`final`, `post_`, `after_` that suggest post-outcome recording. Both are
phrased as "Potential data leakage detected" with an explanation of why the
user should verify manually.

## ML Readiness Score

A transparent, explainable 0–100 heuristic — explicitly documented (in the
API response's `disclaimer` field, and here) as **not** a model-performance
prediction. Weighted breakdown:

| Component | Weight | Inputs |
|---|---|---|
| Data Quality | 30% | average missing %, duplicate row % |
| Feature Quality | 25% | constant/near-constant column ratio, high-cardinality ratio, outlier column count |
| Target Quality | 20% | target-detection confidence, class-imbalance severity penalty |
| Distribution Quality | 15% | skewed-column ratio, high-correlation pair count |
| Leakage Risk | 10% | penalized per leakage warning (starts at 100, −25 per warning up to −70) |

The overall score is the weighted sum. The exact formula lives in
`backend/app/profiling/readiness_score.py` and is unit-tested
(`tests/test_target_and_readiness.py`) to always stay within `[0, 100]`.

## What's sent to the LLM (and what isn't)

See `backend/app/llm/summarizer.py`. The LLM receives: dataset overview,
per-column aggregated stats (no raw values beyond top-3 categorical
examples), the list of detected issues, outlier summaries, high-correlation
pairs, target detection + class imbalance, leakage warnings, and the ML
readiness breakdown. It never receives individual rows or the original
file. The system prompt (`llm/prompts.py`) explicitly instructs the model
not to invent statistics and to use cautious language for target/leakage
claims.
