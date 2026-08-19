# Deployment

## Local development

See the root `README.md` "Running locally" section — `docker compose up
--build` is the fastest path.

## Production deployment (recommended path)

This MVP is intentionally deployable on simple, low-ops infrastructure. A
reasonable first production setup:

1. **Database**: a managed PostgreSQL instance (Railway, Render, Supabase,
   Neon, or AWS RDS). Set `DATABASE_URL` accordingly. Run
   `python -m app.db.init_db` once against it (creates tables + seeds
   plans) — e.g. as a one-off Docker run or a release-phase command.
2. **Backend**: build `docker/backend.Dockerfile` and deploy the image to
   any container host (Railway, Render, Fly.io, AWS ECS/Fargate, a single
   VM behind Caddy/Nginx). Set all backend env vars from `.env.example` —
   at minimum `DATABASE_URL` and a strong random `SECRET_KEY`.
3. **Frontend**: build `docker/frontend.Dockerfile` (or deploy directly to
   Vercel, which is the path of least resistance for Next.js). Set
   `NEXT_PUBLIC_API_URL` to the backend's public URL at build time.
4. **Reverse proxy / TLS**: terminate HTTPS in front of both services (your
   platform's built-in TLS, or Caddy/Nginx + Let's Encrypt on a VM).
5. **Uploads directory**: `UPLOAD_DIR` should point at ephemeral local disk
   (files are deleted right after processing, so no persistent volume is
   required — but see `scripts/cleanup_temp_files.py` for a safety-net cron
   job in case of crashed requests).

## Enabling AI insights (OpenAI)

1. Create an API key at https://platform.openai.com.
2. Set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`, default
   `gpt-4o-mini`) in the backend environment.
3. No code changes needed — `llm/insight_generator.py` automatically uses
   the real API when the key is present, and falls back to a deterministic
   rules-based summary otherwise.

Estimated cost: see the root response's "Estimated infrastructure + LLM
cost per analysis" — roughly $0.001–0.003 per analysis with `gpt-4o-mini`
given the summary sizes this product sends (never the raw dataset).

## Enabling billing (Stripe)

1. Create a Stripe account (or use test mode first).
2. Create two recurring Products/Prices: "Pro" (₹499/month) and "Team"
   (₹1,999/month). Copy their Price IDs into `STRIPE_PRICE_ID_PRO` /
   `STRIPE_PRICE_ID_TEAM`.
3. Copy your Secret Key into `STRIPE_SECRET_KEY`.
4. Create a webhook endpoint in the Stripe dashboard pointing at
   `https://<your-backend-domain>/api/billing/webhook`, subscribed to at
   least `checkout.session.completed`, `customer.subscription.updated`,
   `customer.subscription.deleted`. Copy the signing secret into
   `STRIPE_WEBHOOK_SECRET`.
5. The frontend "Go Pro"/"Contact Sales" pricing CTAs currently link to
   `/register`; wiring them to call `POST /api/billing/checkout/{tier}` and
   redirect to the returned `checkout_url` is a small follow-up once you
   have real Stripe keys to test against (documented here rather than
   built against fake keys, per the "no fake integrations" engineering
   rule).

### Razorpay (planned, India)

`app/billing/stripe_service.py` exposes `create_checkout_session` /
`handle_webhook_event` as the billing interface. To add Razorpay, implement
the same two functions against the Razorpay SDK
(`app/billing/razorpay_service.py`) and branch on a
`PAYMENT_PROVIDER=stripe|razorpay` setting — the rest of the app (usage
enforcement, plan model) is provider-agnostic already.

## Database migrations

The MVP uses `Base.metadata.create_all()` for simplicity (one command, no
migration history to manage yet). `alembic` is already in
`requirements.txt`; once the schema needs a versioned change in production,
run `alembic init` and generate a baseline migration from the current
models before making further changes.

## Scaling beyond the MVP

- Move analysis processing (`services/analysis_pipeline.py`) off the
  request/response cycle into a background worker (Celery + Redis, or RQ)
  once dataset sizes or concurrent upload volume grow — the pipeline
  function is already a pure function of `(bytes, filename)` so this is a
  queue-wiring change, not a rewrite.
- Add Alembic migrations (see above).
- Add object storage (S3-compatible) if you decide to retain original
  uploaded files longer than "until processed" for any plan tier.
