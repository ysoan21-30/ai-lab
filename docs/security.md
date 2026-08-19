# Security

## Authentication & authorization

- Passwords are hashed with bcrypt (via passlib) — never stored or logged in
  plaintext.
- Auth uses short-lived JWT access tokens (default 60 min) plus longer-lived
  refresh tokens (default 30 days), signed with `SECRET_KEY` (HS256).
  **Generate a strong random `SECRET_KEY` for every deployment** — the
  default in `.env.example` is explicitly insecure and only for local dev.
- Every analysis/billing endpoint requires a valid bearer token
  (`app/auth/dependencies.py::get_current_user`); analysis endpoints further
  scope all reads/writes to `Analysis.user_id == current_user.id`, so one
  user can never read or export another user's report (covered by
  `tests/test_api.py::test_list_analyses_returns_only_owner_data` and
  `test_export_csv_requires_ownership`).
- Admin endpoints require `User.is_admin == True`
  (`get_current_admin` dependency).

## File upload safety

- Extension **and** content are validated — `profiling/loader.py` sniffs the
  actual byte signature for XLSX (`PK\x03\x04`) rather than trusting the
  `.xlsx` extension, and rejects files where they disagree.
- File size is checked against the caller's plan limit *before* parsing
  (`billing/usage.py::enforce_upload_size`), returning `413`.
- Empty files, headers-only files, and files with zero parsed columns are
  rejected with a clear `422` and message instead of propagating a pandas
  exception.
- Row/column hard caps (2,000,000 rows / 2,000 columns) protect against
  memory exhaustion from adversarially large files within the size limit.
- Temporary files: uploads are read directly into memory and processed;
  where temp files are written (`services/file_storage.py`), filenames are
  randomly generated (`uuid4`, no user-controlled path component) and
  validated to live inside `UPLOAD_DIR` before deletion — this prevents path
  traversal via a crafted filename.
- **Retention policy**: files are deleted immediately after processing.
  `scripts/cleanup_temp_files.py` is a safety-net cron job that removes
  anything older than `FILE_RETENTION_HOURS` left behind by a crashed
  request.

## Data privacy

- Raw datasets are **never** logged.
- Raw datasets are **never** sent to the LLM — only an aggregated summary
  (see `docs/data-analysis.md`, "What's sent to the LLM").
- See `/privacy` in the frontend (and `docs/../frontend/src/app/privacy`)
  for the full user-facing privacy policy.

## Injection / traversal protection

- SQL: all queries go through SQLAlchemy's ORM with parameterized queries —
  no raw string-interpolated SQL anywhere in the codebase.
- Path traversal: see file upload safety above; there is no endpoint that
  accepts a user-supplied filesystem path.
- Stripe webhook signatures are verified (`stripe.Webhook.construct_event`)
  before any webhook payload is trusted.

## Rate limiting

`slowapi` enforces `RATE_LIMIT_PER_MINUTE` (default 60/min) per client IP
across the API, returning `429` when exceeded.

## Secrets management

- All secrets (`SECRET_KEY`, `OPENAI_API_KEY`, `STRIPE_SECRET_KEY`,
  `STRIPE_WEBHOOK_SECRET`, DB credentials) are read from environment
  variables via `pydantic-settings` (`app/core/config.py`) — never
  hardcoded in source.
- `.env` is gitignored; only `.env.example` (placeholders) is committed.
- In production, prefer your platform's secret manager (e.g. Docker/K8s
  secrets, AWS Secrets Manager, Railway/Render env vars) over a plain `.env`
  file on disk.

## Error handling

A global exception handler (`app/main.py`) catches any unhandled exception,
logs it server-side with full context, and returns a generic user-facing
`500` message — no stack traces or internal details are ever leaked to the
client. The profiling pipeline additionally wraps dataset processing in its
own try/except (`services/analysis_pipeline.py`) so a malformed dataset
marks the `Analysis` row `FAILED` with a clear message rather than crashing
the request.

## CORS

CORS is restricted to `FRONTEND_URL` in production (`ENVIRONMENT=production`)
and permissive (`*`) only in local development, to make local setup easy
without weakening the production posture.

## Known gaps for a production launch (see docs/deployment.md)

- No 2FA / SSO yet.
- No automated dependency vulnerability scanning wired into CI (recommend
  `pip-audit` / `npm audit` / Dependabot before scaling usage).
- No WAF/DDoS layer — rely on your hosting platform's edge protection
  (Cloudflare, AWS ALB, etc.) in production.
