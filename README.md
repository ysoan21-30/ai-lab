# AI Data Profiler

Upload a CSV or Excel dataset and get an automated data-quality, statistical
analysis, ML-readiness, and AI-generated insights report — in minutes.

## Product overview

AI Data Profiler runs a deterministic statistical analysis pipeline over an
uploaded dataset (dimensions, dtypes, missing values, duplicates, outliers,
correlations, target/leakage detection, ML readiness scoring), then sends a
**reduced, aggregated summary** (never raw data) to an LLM to generate a
plain-language report with cleaning recommendations.

Core flow: Landing page → Sign up/Login → Dashboard → Upload → Automated
profiling → AI insights → Cleaning recommendations → ML readiness score →
Download report → Save to account.

See `/docs` for architecture, API reference, the data-analysis methodology,
security posture, and deployment instructions.

## Project structure

```
/frontend    Next.js + TypeScript + Tailwind SaaS UI
/backend     FastAPI app: profiling engine, auth, billing, LLM integration
/database    (schema lives in backend/app/models — see docs/architecture.md)
/docs        Architecture, API, data-analysis, security, deployment docs
/scripts     Admin creation, temp-file cleanup utility scripts
/docker      Dockerfiles; docker-compose.yml lives at the repo root
```

Inside `/backend/app`:

```
api/         FastAPI routers (auth, analyses, billing, admin, health)
auth/        Password hashing, JWT, auth dependencies
billing/     Plan config, usage limits, Stripe integration
core/        Settings/config
db/          SQLAlchemy engine/session, portable UUID type, init/seed script
llm/         Prompt templates, privacy-preserving summarizer, insight generator
models/      SQLAlchemy ORM models
profiling/   The core profiling engine (loader, column stats, quality,
             outliers, correlation, target detection, leakage, ML readiness)
schemas/     Pydantic request/response schemas
services/    Orchestration: analysis pipeline, charts, report export, storage
```

## Technologies used

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Plotly.js
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy 2.0
- **Data processing**: pandas, NumPy, SciPy, scikit-learn
- **Auth**: bcrypt password hashing + JWT access/refresh tokens
- **Database**: PostgreSQL
- **LLM**: OpenAI API (gpt-4o-mini by default), with a deterministic
  rules-based fallback when no API key is configured
- **Payments**: Stripe (structurally implemented; Razorpay planned — see
  `app/billing/stripe_service.py`)
- **Deployment**: Docker + docker-compose

## Running locally

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env          # fill in SECRET_KEY at minimum; others optional
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000 (docs at `/docs`)
- Postgres: localhost:5432

The backend container runs `python -m app.db.init_db` on startup, which
creates tables and seeds the three pricing plans.

### Option B — Run services individually

**Backend**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp ../.env.example ../.env   # edit DATABASE_URL etc.
# Start Postgres yourself, e.g.:
#   docker run -d -p 5432:5432 -e POSTGRES_USER=profiler -e POSTGRES_PASSWORD=profiler -e POSTGRES_DB=ai_data_profiler postgres:16-alpine
python -m app.db.init_db      # creates tables + seeds plans
uvicorn app.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
cp ../.env.frontend.example .env.local
npm run dev
```

### Creating an admin user

```bash
python scripts/create_admin.py admin@example.com yourpassword
```

## Environment variables

See `.env.example` at the repo root for the full list with comments. Key
variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing secret — generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `OPENAI_API_KEY` | Enables real AI insight generation; falls back to a rules-based summary if unset |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PRICE_ID_PRO` / `STRIPE_PRICE_ID_TEAM` | Enables real subscription billing |
| `NEXT_PUBLIC_API_URL` | Frontend → backend API base URL |
| `UPLOAD_DIR`, `FILE_RETENTION_HOURS` | Temp file handling / retention policy |
| `FREE_ANALYSES_PER_MONTH`, `PRO_ANALYSES_PER_MONTH`, `TEAM_ANALYSES_PER_MONTH`, `PRO_PRICE_INR`, `TEAM_PRICE_INR` | Plan configuration |

Never commit a real `.env` file.

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest -q
```

43 tests currently pass, covering: file loading/validation, per-column
profiling, missing-value/duplicate/constant-column/inconsistent-categorical
detection, outlier detection (IQR + Z-score), correlation analysis, target
detection, class imbalance, ML readiness scoring, and the full authenticated
API surface (register/login, upload/analyze, usage limits, ownership
isolation, exports) against an in-memory SQLite database.

Frontend build/type-check:

```bash
cd frontend
npm run build
```

## Docker setup

`docker-compose.yml` at the repo root builds and runs Postgres, the FastAPI
backend, and the Next.js frontend together. See `docs/deployment.md` for
production deployment guidance (this compose file is intended for local
development).

## Known limitations (MVP scope)

- Database migrations use SQLAlchemy `create_all` rather than a full Alembic
  migration history (Alembic is included in requirements for when the schema
  needs versioned migrations in production).
- Stripe billing is fully wired but requires real Stripe API keys/price IDs
  to process payments — see `docs/deployment.md`.
- Razorpay is not yet implemented; the billing layer's interface
  (`create_checkout_session` / `handle_webhook_event`) is designed so a
  Razorpay backend can be added later behind the same shape.
- No email verification / password-reset flow yet (email/password auth with
  JWT is implemented; transactional email is a fast-follow).
- Analyses run synchronously in the request/response cycle rather than via a
  background job queue — fine for MVP dataset sizes (hard-capped at 2M rows /
  2000 columns) but should move to a queue (e.g. Celery/RQ) before scaling to
  much larger files or concurrent load.
- Admin panel and analytics dashboard cover the metrics specified in the
  spec but are intentionally simple (no date-range filtering yet).

## Remaining external setup requirements

1. A PostgreSQL instance (local via Docker Compose, or managed — e.g. RDS,
   Supabase, Railway, Neon).
2. An OpenAI API key for real AI-generated insights (optional — the app
   works without one, using the deterministic fallback).
3. A Stripe account with two recurring Price objects created (Pro, Team) and
   a webhook endpoint pointed at `/api/billing/webhook` for live billing.
4. A domain + TLS termination (e.g. via a reverse proxy or your hosting
   platform) for production deployment.

See `docs/deployment.md` for step-by-step guidance on all of the above.
