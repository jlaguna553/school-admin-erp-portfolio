"""
Base settings shared by every environment.

Architecture notes
------------------
* Multitenancy is **schema-per-tenant** via ``django-tenants``. Every request is
  routed to a Postgres schema by ``TenantMainMiddleware`` based on the request
  host, so application code never filters by tenant by hand.
* ``SHARED_APPS`` live in the ``public`` schema (platform-level data: the tenant
  registry and platform staff). ``TENANT_APPS`` are installed into *each* school
  schema. Apps listed in both get a table in ``public`` and in every tenant.
* Bounded contexts are the ``apps.*`` packages. Distant contexts (e.g. billing
  and academic) must not hold ORM relations to each other -- they reference
  each other by UUID and talk through service functions, so a context can be
  lifted into its own service later without a schema migration.
"""

from datetime import timedelta
from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

# ---------------------------------------------------------------------------
# Paths & environment
# ---------------------------------------------------------------------------
# base.py -> settings/ -> config/ -> apps/api/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-do-not-use-in-prod")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# The tenant is resolved from the request host, so if a reverse proxy or
# ingress sits in front of Django it must forward the original host and this has
# to be on -- otherwise every request would resolve to the proxy, not the school.
#
# Off by default, and only ever safe behind a proxy you control: a client able to
# set X-Forwarded-Host itself could otherwise choose its own tenant.
# ALLOWED_HOSTS still applies on top.
USE_X_FORWARDED_HOST = env.bool("DJANGO_USE_X_FORWARDED_HOST", default=False)

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
# Any app owning models must appear in SHARED_APPS and/or TENANT_APPS -- that is
# what `migrate_schemas` reads to decide which tables land in which schema.
# Listing an app only in INSTALLED_APPS would leave its tables uncreated.
SHARED_APPS = [
    # modeltranslation must precede django.contrib.admin so it can patch the
    # admin forms for translatable fields.
    "modeltranslation",
    "django_tenants",
    # Tenant registry -- public schema only, by definition.
    "apps.tenants",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # Shared building blocks + platform-level user accounts.
    "apps.core",
    "apps.users",
    # Cross-school identity: one credential, plus which schools it may act at.
    # Public schema only -- copying it per tenant would let one school read the
    # membership list of every other.
    "apps.identity",
]

TENANT_APPS = [
    # contenttypes/auth are duplicated per schema so each school owns its own
    # permissions, groups and user rows.
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "rest_framework",
    # Refresh-token blacklist is per-school: revoking a token at one
    # institution must not touch another's.
    "rest_framework_simplejwt.token_blacklist",
    "apps.core",
    "apps.users",
    # Business bounded contexts.
    "apps.authentication",
    "apps.academic",
    "apps.billing",
]

# django-tenants builds INSTALLED_APPS from SHARED_APPS + the TENANT_APPS that
# are not already shared. Order matters, so dedupe while preserving it.
INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]

# ---------------------------------------------------------------------------
# Multitenancy
# ---------------------------------------------------------------------------
TENANT_MODEL = "tenants.Client"
TENANT_DOMAIN_MODEL = "tenants.Domain"
PUBLIC_SCHEMA_NAME = "public"
# Serve a helpful 404 instead of a 500 when a host maps to no tenant.
SHOW_PUBLIC_IF_NO_TENANT_FOUND = False

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    # Must be first: pins the connection to `public` and, crucially, resets it
    # when the request ends. The school is chosen later, from the access token's
    # signed claim -- there is only one hostname, so nothing about the request
    # itself identifies an institution.
    "apps.tenants.middleware.PublicSchemaMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Resolves the active language from Accept-Language / cookie / URL prefix.
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Overrides the language with the authenticated user's saved preference.
    "apps.core.middleware.UserLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://erp:erp@localhost:5432/erp"),
}
# django-tenants ships its own backend that manages the schema search_path.
DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
# Throttle counters live here, so the backend choice has a security consequence:
# the in-memory default is **per process**, which means N gunicorn workers give
# an attacker N times the configured allowance. Set REDIS_URL in any deployment
# running more than one worker.
_redis_url = env("REDIS_URL", default="")
CACHES = {
    "default": (
        {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _redis_url,
        }
        if _redis_url
        else {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "erp-locmem",
        }
    )
}

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "users.User"

# Django's default backend, and only it. Credentials for school staff are not in
# any school's user table any more -- they are a `PlatformIdentity` in the public
# schema, resolved explicitly by `apps.identity.services`, because on a single
# domain there is no host to say which schema to look in. `ModelBackend` remains
# for the platform operators, who are ordinary users of the public schema.
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization -- Spanish is the default, English is fully supported.
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es"
LANGUAGES = [
    ("es", _("Spanish")),
    ("en", _("English")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

MODELTRANSLATION_DEFAULT_LANGUAGE = "es"
MODELTRANSLATION_LANGUAGES = ("es", "en")
# Fall back to Spanish when an English value is missing, and vice versa.
MODELTRANSLATION_FALLBACK_LANGUAGES = ("es", "en")

# ---------------------------------------------------------------------------
# Static & media (tenant-aware storage so schools cannot read each other's files)
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

STORAGES = {
    "default": {"BACKEND": "django_tenants.files.storage.TenantFileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MULTITENANT_RELATIVE_MEDIA_ROOT = "tenants/%s"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # Verifies the token's tenant claim against the schema resolved from the
        # request host before returning a user.
        "apps.authentication.authentication.TenantJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    # Applied per-view (see apps.authentication.views), not globally: every other
    # endpoint requires a bearer token, so the unauthenticated credential
    # endpoints are the ones worth rate limiting.
    "DEFAULT_THROTTLE_RATES": {
        # Per tenant + client address. Kept high on purpose: a school's staff
        # typically share one NAT address, so a tight limit here would lock out
        # the whole institution rather than an attacker.
        "login": env("THROTTLE_LOGIN", default="30/min"),
        # Per tenant + email. This is the anti-brute-force limit, and it is the
        # one that can afford to be strict.
        "login_email": env("THROTTLE_LOGIN_EMAIL", default="10/min"),
        # A legitimate client refreshes on every access-token expiry, and
        # several tabs may do so at once.
        "refresh": env("THROTTLE_REFRESH", default="60/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    # Custom pair serializer embeds tenant_id + roles in the payload.
    "TOKEN_OBTAIN_SERIALIZER": "apps.authentication.serializers.TenantTokenObtainPairSerializer",
}

# ---------------------------------------------------------------------------
# Refresh-token cookie
# ---------------------------------------------------------------------------
# The refresh token is delivered as an httpOnly cookie so JavaScript cannot read
# it. See apps/authentication/cookies.py for why this requires the frontend to
# proxy /api on its own origin.
AUTH_COOKIE_NAME = env("AUTH_COOKIE_NAME", default="erp_refresh")
AUTH_COOKIE_PATH = "/api/v1/auth/"
AUTH_COOKIE_SAMESITE = env("AUTH_COOKIE_SAMESITE", default="Lax")
# Empty means a host-only cookie: returned only to the exact host that set it.
# That is the safest default and works when the app proxies /api on its own
# origin. Set a parent domain (".example.com") only if the API genuinely lives on
# a different subdomain from the app -- it then offers the cookie to *every*
# subdomain, which is a real widening of exposure.
AUTH_COOKIE_DOMAIN = env("AUTH_COOKIE_DOMAIN", default="") or None
# Must be True wherever the site is served over HTTPS; prod.py forces it on.
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=False)
# Also return the refresh token in the login response body. Off for browsers --
# that would defeat the httpOnly cookie -- but needed by native clients.
AUTH_REFRESH_IN_BODY = env.bool("AUTH_REFRESH_IN_BODY", default=False)

SPECTACULAR_SETTINGS = {
    "TITLE": "School Administration ERP API",
    "DESCRIPTION": (
        "Multi-tenant, internationalized ERP for educational institutions. "
        "Each school is isolated in its own Postgres schema and resolved from "
        "the request host."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v[0-9]+",
    "SORT_OPERATIONS": True,
    # Four models call a field `status` and mean four different things. Left
    # alone, drf-spectacular breaks the tie with a hash -- `StatusA87Enum` --
    # and the generated TypeScript names a set of attendance marks after a
    # checksum. Naming them here is the difference between a usable client and
    # one nobody can read.
    "ENUM_NAME_OVERRIDES": {
        "UserRoleEnum": "apps.users.models.UserRole.choices",
        "AttendanceStatusEnum": "apps.academic.models.AttendanceStatus.choices",
        "SessionStatusEnum": "apps.academic.models.SessionStatus.choices",
        "WeekdayEnum": "apps.academic.models.Weekday.choices",
    },
}

# ---------------------------------------------------------------------------
# CORS -- the Next.js frontend runs on a different origin in development.
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
