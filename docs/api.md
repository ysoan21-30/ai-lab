# API Reference

Base URL: `http://localhost:8000` (local) — interactive OpenAPI docs are
always available at `/docs` (Swagger UI) and `/redoc`.

All authenticated endpoints require `Authorization: Bearer <access_token>`.

## Auth

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Create an account. Body: `{email, password, full_name?}`. Returns access + refresh tokens and the user. |
| POST | `/api/auth/login` | Body: `{email, password}`. Returns access + refresh tokens. |
| POST | `/api/auth/refresh` | Query/body: `refresh_token`. Returns a new token pair. |
| GET | `/api/auth/me` | Returns the current authenticated user. |

## Analyses

| Method | Path | Description |
|---|---|---|
| POST | `/api/analyses` | Multipart upload (`file`). Runs the full profiling + AI pipeline synchronously and returns the completed `AnalysisDetail`. Enforces the caller's monthly usage limit and plan upload-size limit. |
| GET | `/api/analyses` | Lists the current user's analyses (most recent first, capped at 100). |
| GET | `/api/analyses/usage` | Returns `{plan, analyses_used_this_month, analyses_limit, max_upload_mb}`. |
| GET | `/api/analyses/{id}` | Full analysis detail (profile, quality, correlation, target, ML readiness, AI insights, charts). 404 if not owned by the caller. |
| POST | `/api/analyses/{id}/target` | Body: `{column}`. Manually overrides the detected target column. |
| DELETE | `/api/analyses/{id}` | Deletes an analysis. |
| GET | `/api/analyses/{id}/export/json` | Full analysis as JSON. |
| GET | `/api/analyses/{id}/export/csv` | Data-quality issues as a CSV file. |
| GET | `/api/analyses/{id}/export/pdf` | Formatted PDF report. **Requires Pro or Team plan.** |

## Billing

| Method | Path | Description |
|---|---|---|
| GET | `/api/billing/plans` | Public: returns the three plan configs (features, price, limits). |
| POST | `/api/billing/checkout/{tier}` | Creates a Stripe Checkout session for `pro` or `team` and returns `{checkout_url}`. Requires `STRIPE_SECRET_KEY` + a price ID to be configured. |
| POST | `/api/billing/webhook` | Stripe webhook receiver — verifies the signature and updates the user's plan on `checkout.session.completed` / subscription cancellation events. |

## Admin

| Method | Path | Description |
|---|---|---|
| GET | `/api/admin/overview` | Admin-only. Aggregate metrics: user counts, analysis counts, average processing time, error count, subscription counts, estimated MRR, total LLM cost, dataset size distribution. Never returns raw dataset contents. |

## Errors

Errors return `{"detail": "..."}` (or a list of validation errors for 422s
from request validation). Notable status codes:

- `400` — malformed request (unsupported file extension, invalid target column, etc.)
- `401` — missing/invalid/expired token
- `402` — monthly analysis limit reached, or a Pro/Team-only feature requested on Free
- `403` — admin-only endpoint
- `404` — resource not found or not owned by the caller
- `413` — file exceeds the plan's upload size limit
- `422` — the uploaded file couldn't be parsed (corrupted, empty, no data rows, etc.)
- `429` — rate limit exceeded (`RATE_LIMIT_PER_MINUTE`, default 60/min per IP)
- `500` — unexpected server error (logged; user-friendly message returned, no stack trace leaked)
