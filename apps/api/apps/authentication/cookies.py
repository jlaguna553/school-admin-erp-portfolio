"""
Refresh-token cookie handling.

Why a cookie at all: an access token held only in JavaScript memory dies with the
tab, but the refresh token has to survive a reload. Keeping it in
``localStorage`` means any successful XSS can read it and mint access tokens
indefinitely. An ``httpOnly`` cookie is unreachable from JavaScript, so the same
XSS can only act while the page is open.

Why this works at all: the cookie is only sent if the API is **same-site** with
the page. ``localhost:3000`` and ``northfield.localhost:8000`` are *different*
sites (``localhost`` is a public suffix, so the registrable domains differ), so a
``SameSite=Lax`` cookie would silently never be sent. The frontend therefore
proxies ``/api`` to Django on its own origin -- see ``apps/web/next.config.ts`` --
which also matches the production topology of one hostname per school.

``SameSite=Lax`` is what protects the refresh endpoint from CSRF: browsers do not
attach Lax cookies to cross-site POSTs, so another origin cannot silently spend
the refresh token.
"""

from django.conf import settings
from rest_framework.response import Response


def cookie_name() -> str:
    return settings.AUTH_COOKIE_NAME


def set_refresh_cookie(response: Response, token: str) -> Response:
    """Attach the refresh token as an httpOnly cookie."""
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        # Scoped to the auth endpoints, so the token is not attached to every
        # ordinary API request.
        path=settings.AUTH_COOKIE_PATH,
        # Normally None (host-only). A parent domain widens it to every
        # subdomain, which is only worth doing for a split app/API deployment.
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    return response


def clear_refresh_cookie(response: Response) -> Response:
    # Path, domain and samesite must match the cookie that was set, or the
    # browser treats this as a different cookie and the original survives.
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path=settings.AUTH_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return response


def read_refresh_token(request) -> str | None:  # noqa: ANN001
    """Return the refresh token from the request body, else the cookie.

    Body first so non-browser clients (a future React Native app, scripts) keep
    working unchanged; the cookie is what browsers use.
    """
    from_body = request.data.get("refresh") if hasattr(request, "data") else None
    if from_body:
        return str(from_body)
    return request.COOKIES.get(settings.AUTH_COOKIE_NAME)
