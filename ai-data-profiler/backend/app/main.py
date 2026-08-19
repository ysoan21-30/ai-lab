"""FastAPI application entrypoint."""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api import (
    admin_routes, analysis_routes, apikey_routes, audit_routes, auth_routes,
    billing_routes, comparison_routes, connector_routes, health_routes,
    rules_routes, schedule_routes, share_routes, team_routes, webhook_routes,
)
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_data_profiler")

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])

app = FastAPI(
    title="AI Data Profiler API",
    description="Upload a dataset, get an automated data-quality and ML-readiness report.",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# NOTE: setting app.state.limiter and default_limits above does nothing on
# its own -- slowapi only enforces rate limits once this middleware is
# registered. Without it, requests were never actually throttled.
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url] if settings.is_production else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected server error occurred. Please try again."},
    )


app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(analysis_routes.router)
app.include_router(billing_routes.router)
app.include_router(comparison_routes.router)
app.include_router(apikey_routes.router)
app.include_router(connector_routes.router)
app.include_router(schedule_routes.router)
app.include_router(team_routes.router)
app.include_router(share_routes.router)
app.include_router(rules_routes.router)
app.include_router(audit_routes.router)
app.include_router(webhook_routes.router)
app.include_router(admin_routes.router)


@app.get("/")
def root():
    return {"name": "AI Data Profiler API", "status": "running", "docs": "/docs"}
