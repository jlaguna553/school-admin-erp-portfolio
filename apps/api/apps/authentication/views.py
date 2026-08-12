from typing import Any

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenVerifyView

from apps.identity import services as identity_services
from apps.identity.models import PlatformIdentity

from .cookies import clear_refresh_cookie, read_refresh_token, set_refresh_cookie
from .serializers import LoginSerializer, LogoutSerializer, SwitchSchoolSerializer
from .tenant import activate_schema_from_token
from .throttling import LoginEmailRateThrottle, LoginRateThrottle, RefreshRateThrottle


@extend_schema(
    summary="Log in",
    description=(
        "Exchanges credentials for an access token.\n\n"
        "One hostname serves every institution, so the school is not resolved "
        "from the request: the credential is looked up platform-wide and the "
        "response says which schools the account is registered at. The session "
        "opens at the one used last, and `schools` lists them all -- a client "
        "with one entry renders no switcher, but still knows where it is. It is "
        "empty only for a platform operator, who is above every school.\n\n"
        "The **refresh token is returned as an httpOnly cookie**, not in the body, "
        "so JavaScript cannot read it. Set `AUTH_REFRESH_IN_BODY=True` to also "
        "include it for native clients that cannot use cookies."
    ),
)
class LoginView(APIView):
    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()
    # Two limits, because the threats differ: a generous per-address cap (a
    # school shares one NAT egress) plus a strict per-account cap, which is the
    # dimension brute force actually walks.
    throttle_classes = (LoginRateThrottle, LoginEmailRateThrottle)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)
        response = Response(data, status=status.HTTP_200_OK)

        refresh = data.get("refresh")
        if refresh:
            set_refresh_cookie(response, refresh)
            if not settings.AUTH_REFRESH_IN_BODY:
                # Keeping it in the body as well would defeat the httpOnly cookie.
                del response.data["refresh"]

        return response


@extend_schema(
    summary="Switch to another of your schools",
    request=SwitchSchoolSerializer,
    responses={200: OpenApiResponse(description="A token scoped to the chosen school.")},
)
class SwitchSchoolView(APIView):
    """Re-issue the session against a different school.

    Under the old host-per-school model this was a navigation to another origin,
    which meant signing in again -- the refresh cookie is host-only. On one
    domain the session stays where it is and only the tenant claim changes, so
    switching costs a round trip instead of a password.

    The membership is re-read here rather than trusted from the list the client
    was handed at login: that list may be minutes old, and access can be revoked
    in between.
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = SwitchSchoolSerializer

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = SwitchSchoolSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identity_id = getattr(request.user, "identity_id", None)
        if not identity_id:
            raise ValidationError({"tenant_id": _("This account belongs to a single school.")})

        identity = PlatformIdentity.objects.filter(pk=identity_id, is_active=True).first()
        if identity is None:
            raise ValidationError({"tenant_id": _("This account belongs to a single school.")})

        membership = identity_services.membership_for_tenant(
            identity, serializer.validated_data["tenant_id"]
        )
        if membership is None:
            raise ValidationError({"tenant_id": _("You are not registered at this institution.")})

        login = LoginSerializer()
        user = identity_services.enter_school(identity, membership)
        identity_services.remember_entry(identity, membership)

        schools = [
            identity_services.school_payload(candidate, membership.tenant.schema_name)
            for candidate in identity_services.memberships_for(identity)
        ]

        data = login._payload(
            user=user, tenant=membership.tenant, role=membership.role, schools=schools
        )

        response = Response(data, status=status.HTTP_200_OK)
        refresh = data.get("refresh")
        if refresh:
            set_refresh_cookie(response, refresh)
            if not settings.AUTH_REFRESH_IN_BODY:
                del response.data["refresh"]
        return response


@extend_schema(
    summary="Refresh the access token",
    description=(
        "Reads the refresh token from the request body if present, otherwise from "
        "the httpOnly cookie set at login. Rotation is enabled, so a new cookie is "
        "issued on every call and the previous token is blacklisted."
    ),
    request=None,
    responses={200: OpenApiResponse(description="A new access token.")},
)
class RefreshView(APIView):
    """Cookie-aware refresh.

    Not a subclass of ``TokenRefreshView``: that view requires ``refresh`` in the
    request body, which a browser client no longer has -- the token is in a
    cookie it cannot read.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (RefreshRateThrottle,)
    serializer_class = TokenRefreshSerializer

    def _unauthenticated(self, detail: str) -> Response:
        """401 plus a cookie reset.

        DRF downgrades an ``AuthenticationFailed`` to 403 when the view declares
        no authenticators (it has no ``WWW-Authenticate`` header to offer), which
        would be misleading here -- a spent or malformed refresh token means
        "authenticate again", not "forbidden". The status is therefore set
        explicitly.

        The cookie is cleared at the same time: leaving a token the server has
        already rejected in place makes the browser replay it on every load.
        """
        response = Response({"detail": detail}, status=status.HTTP_401_UNAUTHORIZED)
        return clear_refresh_cookie(response)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        token = read_refresh_token(request)
        if not token:
            return self._unauthenticated(str(_("No refresh token was provided.")))

        # Rotation blacklists the old token and records the new one, both in the
        # schema that owns the user. Skipping this would revoke nothing and
        # write a row that fails its foreign key.
        activate_schema_from_token(token)

        serializer = TokenRefreshSerializer(data={"refresh": token})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken, ValidationError):
            return self._unauthenticated(str(_("The session has expired. Please sign in again.")))

        data = dict(serializer.validated_data)
        rotated = data.pop("refresh", None)

        response = Response(data, status=status.HTTP_200_OK)
        if rotated:
            set_refresh_cookie(response, rotated)
            if settings.AUTH_REFRESH_IN_BODY:
                response.data["refresh"] = rotated

        return response


@extend_schema(summary="Verify a token")
class VerifyView(TokenVerifyView):
    permission_classes = (AllowAny,)
    throttle_classes = (RefreshRateThrottle,)


class LogoutView(APIView):
    """Blacklists the refresh token and clears the cookie."""

    permission_classes = (IsAuthenticated,)
    serializer_class = LogoutSerializer

    @extend_schema(
        summary="Log out",
        description=(
            "Blacklists the refresh token so it cannot be replayed, and clears the "
            "httpOnly cookie. The token is taken from the body if supplied, "
            "otherwise from the cookie."
        ),
        request=LogoutSerializer,
        responses={204: None},
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        token = read_refresh_token(request)
        if token:
            # Blacklisting in the wrong schema silently revokes nothing.
            activate_schema_from_token(token)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        # The cookie is cleared even when the token is already invalid: the user
        # asked to leave, and leaving a dead cookie behind only causes confusion.
        clear_refresh_cookie(response)

        if token:
            serializer = LogoutSerializer(data={"refresh": token})
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return response
