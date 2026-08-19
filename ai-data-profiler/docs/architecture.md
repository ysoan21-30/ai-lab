# Architecture

## High-level flow

```
Browser (Next.js)
    │  fetch/axios, JWT bearer token
    ▼
FastAPI backend
    │
    ├── auth/          register, login, JWT issuance/verification
    ├── analyses upload → profiling/ (deterministic pipeline)
    │                       │
    │                       ▼
    │                   llm/ (privacy-preserving summary → OpenAI or fallback)
    │                       │
    │                       ▼
    │                   services/analysis_pipeline.py persists results
    ├── billing/        Stripe checkout + webhook, usage limits
    └── admin/          aggregate metrics (no raw data exposure)
    │
    ▼
PostgreSQL (users, analyses, usage_records, plans, api_keys)
```

## Why a monolithic FastAPI service (not microservices) for the MVP

Per the engineering brief ("do not over-engineer the first version"), the
whole backend is one deployable FastAPI app. Internally it's organized into
clearly separated modules (`profiling`, `llm`, `billing`, `auth`, `api`,
`services`) so any of them can be extracted into a separate service later
(e.g. moving `profiling` into a queue-backed worker) without a rewrite.

## The profiling engine (`backend/app/profiling/`)

This is the product's core IP. It's a pure-Python/pandas pipeline with no
external service dependencies, which makes it fast, deterministic, and
testable in isolation:

1. **`loader.py`** — safely loads CSV/XLSX from raw bytes. Never trusts the
   file extension: sniffs the actual byte signature (`PK\x03\x04` for
   xlsx), tries multiple encodings for CSV, caps rows/columns, and raises a
   typed `DatasetLoadError` with a user-facing message for every failure
   mode instead of letting an exception propagate.
2. **`column_profiler.py`** — per-column statistics (dtype classification,
   missing/unique counts, numeric distribution stats via SciPy, categorical
   top-values/cardinality, datetime range checks).
3. **`quality.py`** — rule-based detectors for missing-value severity,
   duplicate rows/IDs, constant/near-constant columns, high cardinality,
   potential ID columns, inconsistent categorical casing, and domain-specific
   invalid-value heuristics (negative ages, out-of-range percentages, etc).
4. **`outliers.py`** — IQR and Z-score outlier detection, report-only (never
   auto-removes data).
5. **`correlation.py`** — Pearson + Spearman correlation matrices and a
   configurable high-correlation threshold (default `0.90`).
6. **`target_detection.py`** — heuristic target-column and class-imbalance
   detection. Always phrased as "potential"/"most likely" — never asserted.
7. **`leakage.py`** — conservative potential-data-leakage warnings based on
   near-perfect target correlation and suspicious column-name patterns.
8. **`readiness_score.py`** — the transparent, weighted 0–100 ML Readiness
   Score (Data Quality 30%, Feature Quality 25%, Target Quality 20%,
   Distribution Quality 15%, Leakage Risk 10%), documented as a heuristic,
   not a performance prediction.
9. **`orchestrator.py`** — runs the above in sequence and returns one
   structured `profile` dict consumed by the LLM summarizer, chart builder,
   and API layer.

## The AI insight layer (`backend/app/llm/`)

- **`summarizer.py`** builds a small, aggregated JSON summary from the full
  profile — column-level stats and detected issues, never raw rows.
- **`prompts.py`** defines a system prompt that explicitly forbids inventing
  statistics and requires a structured JSON response.
- **`insight_generator.py`** calls OpenAI if `OPENAI_API_KEY` is set; if it's
  unset, or the API call fails for any reason, it falls back to a real,
  fully-functional deterministic rules-based summary generated directly from
  the same structured data — so the product never depends on a working LLM
  key to be useful, and never fails silently.

## Data model (`backend/app/models/models.py`)

- `User` — auth + plan tier + Stripe customer/subscription IDs.
- `Analysis` — one row per uploaded dataset's analysis; stores results as
  JSON columns (profile, quality, correlation, target, ML readiness, AI
  insights, charts) plus denormalized scores for fast dashboard listing.
- `UsageRecord` — one row per analysis run, used for monthly usage-limit
  enforcement and admin analytics.
- `Plan` — DB-backed plan configuration (seeded from `billing/plans.py`
  defaults, which themselves read from environment variables) so pricing
  isn't hardcoded across the app.
- `ApiKey` — scaffold for Team-plan API access.

IDs use a portable `GUID` type (`db/types.py`) that maps to native
PostgreSQL `UUID` in production and `CHAR(36)` under SQLite in tests, so the
same models work in both environments without special-casing.

## Frontend (`frontend/src/`)

Next.js App Router with a small set of route segments matching the required
user flow: `/` (landing), `/register`, `/login`, `/dashboard`,
`/upload`, `/analysis/[id]` (the report viewer), `/admin`, `/privacy`.
`lib/auth.tsx` provides a React context wrapping JWT storage + the
authenticated user; `components/RequireAuth.tsx` gates protected routes.
Charts are rendered client-side only via a dynamically-imported Plotly
wrapper (`components/PlotlyChart.tsx`) to avoid SSR issues with `window`.
