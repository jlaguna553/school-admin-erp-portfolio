"""Development settings."""

from .base import *  # noqa: F403
from .base import INSTALLED_APPS, env
from .base import REST_FRAMEWORK as BASE_REST_FRAMEWORK

DEBUG = True

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", ".localhost"],
)

# Tenants are resolved by host, so every school gets a subdomain in development
# (e.g. northfield.localhost:8000). Browsers resolve *.localhost automatically.
# Any localhost port is allowed here so a second dev server (or a colleague's
# non-default port) works without editing settings. Production pins exact
# origins from the environment instead -- see prod.py.
CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://([\w-]+\.)?localhost:\d+$"]
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])

INSTALLED_APPS = INSTALLED_APPS + ["django_extensions"]

# Emails go to the console instead of a real SMTP server.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Browsable API is convenient locally, but never in production.
REST_FRAMEWORK = {
    **BASE_REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}
