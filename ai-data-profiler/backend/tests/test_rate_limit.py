"""Regression test: setting app.state.limiter and Limiter(default_limits=...)
alone does NOT enforce anything in slowapi -- SlowAPIMiddleware must also be
registered on the app. It previously wasn't, so no request was ever actually
throttled despite rate-limit configuration existing end to end.
"""
from slowapi.middleware import SlowAPIMiddleware

from app.main import app


def test_rate_limit_middleware_is_registered():
    middleware_classes = [m.cls for m in app.user_middleware]
    assert SlowAPIMiddleware in middleware_classes, (
        "SlowAPIMiddleware must be registered via app.add_middleware for "
        "the configured Limiter (app.state.limiter / default_limits) to "
        "actually enforce rate limits on incoming requests."
    )
