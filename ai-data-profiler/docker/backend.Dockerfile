FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY scripts ./scripts

RUN mkdir -p /tmp/ai-data-profiler-uploads

# PORT is injected by most PaaS providers (Railway, Render, Fly, Heroku).
# Falling back to 8000 keeps local/docker-compose behaviour unchanged.
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f "http://localhost:${PORT}/api/health" || exit 1

# NOTE: init_db is run here, not only in docker-compose. Without it, a fresh
# production database has no tables and every DB-backed endpoint 500s.
# create_all is idempotent, so re-running on each boot is safe.
CMD ["sh", "-c", "python -m app.db.init_db && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
