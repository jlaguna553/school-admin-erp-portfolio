from typing import Any

from django.conf import settings
from django.db import connection
from django.utils import translation
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import BrandingSerializer, HealthSerializer


class HealthCheckView(APIView):
    """Unauthenticated liveness probe that also reports tenant resolution.

    Useful during onboarding: hitting it on a school's host confirms the domain
    is mapped to the right Postgres schema before any real request is made.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = HealthSerializer

    @extend_schema(
        responses={200: HealthSerializer},
        examples=[
            OpenApiExample(
                "Resolved tenant",
                value={
                    "status": "ok",
                    "schema": "northfield",
                    "language": "es",
                    "available_languages": ["es", "en"],
                },
                response_only=True,
            )
        ],
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        payload = {
            "status": "ok",
            "schema": connection.schema_name,
            "language": translation.get_language() or settings.LANGUAGE_CODE,
            "available_languages": [code for code, _label in settings.LANGUAGES],
        }
        return Response(payload, status=status.HTTP_200_OK)


class BrandingView(APIView):
    """The institution's name and brand colour, resolved from the request host.

    Deliberately unauthenticated. Branding has to be on screen *before* anyone
    signs in -- the login page is where a school's identity matters most -- and
    the frontend renders it server-side to avoid a flash of the default palette.
    Nothing here is a secret: it is the same name and colour every visitor to
    that hostname already sees.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()
    serializer_class = BrandingSerializer

    @extend_schema(responses={200: BrandingSerializer})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        tenant = getattr(connection, "tenant", None)
        payload = {
            "name": getattr(tenant, "name", None) or "",
            "schema": connection.schema_name,
            # The model default, repeated here for the placeholder tenant that
            # `schema_context` installs outside a request.
            "brand_color": getattr(tenant, "brand_color", None) or "#1d4ed8",
            "default_language": getattr(tenant, "default_language", None) or "es",
        }
        return Response(payload, status=status.HTTP_200_OK)
