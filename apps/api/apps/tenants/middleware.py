"""
Schema lifecycle for a single-domain deployment.

The whole platform is served from one hostname, so there is nothing in the URL
or the ``Host`` header that says which school a request is for. Every request
therefore starts on ``public``, and the school is selected later -- from the
signed ``tenant_schema`` claim in the access token, by
:class:`apps.authentication.authentication.TenantJWTAuthentication`.

This replaces django-tenants' ``TenantMainMiddleware``, whose entire job was to
map a hostname onto a schema.

The reset in ``finally`` is the part that matters. Database connections are
reused across requests by the same worker, and ``search_path`` is session state:
a request that ended while pointed at a school would hand that school's schema
to whoever the worker serves next. Losing an exception here would be a
cross-tenant data leak, so the reset is unconditional and outside any
``except``.
"""

from collections.abc import Callable

from django.db import connection
from django.http import HttpRequest, HttpResponse


class PublicSchemaMiddleware:
    """Pin every request to ``public``, and put it back when the request ends."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        connection.set_schema_to_public()
        try:
            return self.get_response(request)
        finally:
            # Runs even when the view raised, and even when a response was
            # already streamed: the next request must never inherit a schema.
            connection.set_schema_to_public()
