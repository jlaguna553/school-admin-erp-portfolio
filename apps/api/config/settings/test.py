"""
Test settings.

Kept separate from ``dev`` so the suite never depends on the ambient
environment: ``DJANGO_ALLOWED_HOSTS`` differs between a laptop, the Docker dev
stack and CI, and tenant tests drive requests at arbitrary hosts.
"""

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK as BASE_REST_FRAMEWORK

DEBUG = False

# At least 32 bytes, or PyJWT warns that the HMAC key is too short for SHA256.
SECRET_KEY = "test-only-not-a-secret-padded-to-32-bytes-minimum"

# Tenants are addressed by hostname, and each test invents its own
# (``alpha.testserver``, ``beta.testserver``, ...). Host validation is a
# deployment concern, not something these tests are asserting.
ALLOWED_HOSTS = ["*"]

CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]
CORS_ALLOWED_ORIGIN_REGEXES = []

# The suite creates a lot of users, and PBKDF2 dominates the runtime.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# JSON only -- the browsable renderer would make `response.data` assertions
# depend on content negotiation.
REST_FRAMEWORK = {
    **BASE_REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    # Throttling off by default: fixtures log in for nearly every test, which
    # would exhaust the login allowance and fail unrelated tests. The throttle
    # tests re-enable it explicitly with override_settings.
    "DEFAULT_THROTTLE_RATES": {"login": None, "login_email": None, "refresh": None},
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Keep test output readable; the exception handler logs warnings on purpose.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "loggers": {
        "apps.core.exceptions": {"handlers": ["null"], "propagate": False},
        "django.request": {"handlers": ["null"], "propagate": False},
    },
}
