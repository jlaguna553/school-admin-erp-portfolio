"""Production settings. Every secret must come from the environment."""

from .base import *  # noqa: F403
from .base import MIDDLEWARE as BASE_MIDDLEWARE
from .base import REST_FRAMEWORK as BASE_REST_FRAMEWORK
from .base import STORAGES as BASE_STORAGES
from .base import env

DEBUG = False

# No default: the process must fail loudly rather than boot insecurely.
SECRET_KEY = env("DJANGO_SECRET_KEY")

# Optional, because the frontend's hostname is not known until it is deployed --
# and requiring it here meant the very first deploy could never boot, which
# looks like a broken image rather than a missing variable.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# Render (and similar) inject the service's own hostname. Adding it lets the
# container start and pass its health check before anything else is configured;
# the frontend's host still has to be added explicitly.
_platform_host = env("RENDER_EXTERNAL_HOSTNAME", default="")
if _platform_host and _platform_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_platform_host)
# Empty is correct for the proxied topology: the browser only ever calls the
# frontend's origin, so it never makes a cross-origin request.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# Django checks the Origin header against this for unsafe requests, and behind a
# proxy the origin is the frontend's, not the API's. Without it the admin login
# and any session-authenticated POST fail CSRF verification.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- Static files -----------------------------------------------------------
# WhiteNoise serves collected static files (the admin and DRF's browsable
# assets) straight from gunicorn, so the container needs no nginx sidecar.
# It must sit immediately after SecurityMiddleware.
_security_index = BASE_MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
MIDDLEWARE = [
    *BASE_MIDDLEWARE[: _security_index + 1],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *BASE_MIDDLEWARE[_security_index + 1 :],
]

STORAGES = {
    **BASE_STORAGES,
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# HTTPS / transport hardening
# Defaults to on. Set DJANGO_SECURE_SSL_REDIRECT=False to exercise the
# production image locally over plain http -- with it on, every request would
# 301 to an https port that is not listening.
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31_536_000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# The refresh cookie must never travel in clear text. Defaults on, and
# overridable only so the production image can be smoke-tested locally over
# plain http -- where a Secure cookie is set but never sent back. Leave it
# unset in any real deployment.
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=True)
X_FRAME_OPTIONS = "DENY"

# JSON only -- no browsable API in production.
REST_FRAMEWORK = {
    **BASE_REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "propagate": False},
    },
}
