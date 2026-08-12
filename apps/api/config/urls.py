"""
The URL configuration. One hostname serves the whole platform.

There used to be two of these -- one for a school's host, one for the
platform's -- selected by whichever schema the hostname resolved to. With a
single domain there is no hostname to select on, so school routes and
platform routes sit side by side and *permissions* do the gating they always
really did: `IsPlatformAdmin` already required the caller to be platform staff,
and every school route already required a tenant to be selected by the caller's
token.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from apps.core.views import BrandingView

api_v1_patterns = [
    path("auth/", include("apps.authentication.urls")),
    # School-scoped. Which school is decided by the caller's access token; with
    # no token, or one naming a school they have no membership at, these are
    # unreachable rather than defaulting to anything.
    path("users/", include("apps.users.urls")),
    path("academic/", include("apps.academic.urls")),
    path("billing/", include("apps.billing.urls")),
    # Platform-scoped: operators only, enforced by `IsPlatformAdmin`.
    path("tenants/", include("apps.tenants.urls")),
    path("identities/", include("apps.identity.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
    # Health probe -- unauthenticated, reports the resolved tenant schema.
    path("api/health/", include("apps.core.urls")),
    # Unauthenticated platform branding. A school's own colour is no longer
    # servable here -- one hostname cannot say which school is being visited --
    # so it is applied after signing in, from the token.
    path("api/v1/branding/", BrandingView.as_view(), name="branding"),
    # OpenAPI 3.0
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
