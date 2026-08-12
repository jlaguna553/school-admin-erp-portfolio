"""
JWT issuance for a single-domain platform.

The access token carries ``tenant_schema``, ``tenant_id``, ``user_id`` and
``roles``. On this deployment the tenant claim is not a convenience: it is *how*
a request says which school it is for, because one hostname serves all of them.

That does not make it an authority. Every request re-reads the membership from
the database before honouring the claim -- see
:class:`apps.authentication.authentication.TenantJWTAuthentication` -- so a
token outlives the access it describes by at most one request.
"""

from typing import Any

from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework_simplejwt.tokens import RefreshToken, Token

from apps.core import modules as core_modules
from apps.identity import services as identity_services
from apps.identity.models import PlatformIdentity


class InvalidCredentials(APIException):
    """Wrong email or wrong password -- deliberately indistinguishable.

    A plain ``APIException`` rather than DRF's ``AuthenticationFailed``: the
    login view declares no authenticators, and DRF downgrades that exception to
    403 when it has no ``WWW-Authenticate`` scheme to offer. 403 would tell a
    caller their credentials were accepted and merely insufficient.
    """

    status_code = 401
    default_detail = _("No active account found with the given credentials.")
    default_code = "authentication_failed"


class LoginSerializer(serializers.Serializer):
    """Email and password, resolved into a person and the school they enter.

    Two kinds of account sign in here and the order is deliberate. Most people
    are a :class:`PlatformIdentity` -- one credential, one or more schools.
    Platform operators are ordinary users of the public schema with no identity
    at all, and are tried second, so an operator who also works at a school gets
    their school account rather than silently landing in the console.
    """

    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        email = attrs["email"]
        password = attrs["password"]

        identity = identity_services.authenticate_identity(email, password)
        if identity is not None:
            return self._sign_in_to_school(identity)

        operator = authenticate(request=self.context.get("request"), email=email, password=password)
        if operator is not None and operator.is_active:
            return self._sign_in_to_platform(operator)

        raise InvalidCredentials()

    # -- the two entry paths -------------------------------------------------
    def _sign_in_to_school(self, identity: PlatformIdentity) -> dict[str, Any]:
        memberships = identity_services.memberships_for(identity)
        # Raises 403 rather than 401 when nothing opens: the credentials were
        # right, there is just nowhere to go. Saying so plainly beats "invalid
        # password", which would send someone to reset a password that works.
        membership, user = identity_services.open_first_available(identity, memberships)
        identity_services.remember_entry(identity, membership)
        identity.touch_login()

        schools = [
            identity_services.school_payload(candidate, membership.tenant.schema_name)
            for candidate in memberships
        ]

        # Minted while the connection is still on the school's schema.
        # SimpleJWT records the outstanding token with a ForeignKey to the user,
        # and that user row exists only here -- writing it on `public` fails the
        # key. `apps.authentication.tenant` is how refresh and logout find their
        # way back to this same schema.
        return self._payload(
            user=user,
            tenant=membership.tenant,
            role=membership.role,
            schools=schools,
        )

    def _sign_in_to_platform(self, operator: Any) -> dict[str, Any]:
        return self._payload(user=operator, tenant=None, role=operator.role, schools=[])

    # -- token + response ----------------------------------------------------
    def _payload(
        self, *, user: Any, tenant: Any, role: str, schools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        refresh = self._token_for(user, tenant, role)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.get_full_name(),
                "role": role,
                "roles": user.roles,
                "language": user.language,
            },
            "tenant": {
                "id": str(tenant.id) if tenant is not None else None,
                "schema": tenant.schema_name if tenant is not None else "public",
                "name": tenant.name if tenant is not None else None,
                "default_language": tenant.default_language if tenant is not None else None,
                "default_currency": tenant.default_currency if tenant is not None else None,
                "brand_color": tenant.brand_color if tenant is not None else None,
                # What this school actually runs. The interface hides what is
                # switched off rather than offering screens the API will refuse.
                "modules": (
                    core_modules.enabled_modules(tenant.disabled_modules)
                    if tenant is not None
                    else []
                ),
            },
            # Every school this account may work at, current one included.
            # Empty only for a platform operator, who is above all of them.
            "schools": schools,
        }

    @staticmethod
    def _token_for(user: Any, tenant: Any, role: str) -> Token:
        refresh = RefreshToken.for_user(user)
        refresh["tenant_schema"] = tenant.schema_name if tenant is not None else "public"
        refresh["tenant_id"] = str(tenant.id) if tenant is not None else None
        refresh["tenant_name"] = tenant.name if tenant is not None else None
        refresh["tenant_currency"] = tenant.default_currency if tenant is not None else None
        refresh["brand_color"] = tenant.brand_color if tenant is not None else None
        # In the token so a reload renders the right navigation on first paint:
        # a refresh returns only an access token, with no `tenant` payload.
        refresh["modules"] = (
            core_modules.enabled_modules(tenant.disabled_modules) if tenant is not None else []
        )
        refresh["roles"] = [role] if role else []
        refresh["email"] = user.email
        refresh["language"] = user.language
        return refresh


class SwitchSchoolSerializer(serializers.Serializer):
    """Move an existing session to another of the person's schools.

    A re-issue rather than a fresh login. It used to be a navigation to another
    hostname, which meant signing in again; with one domain the session stays
    put and only the tenant claim changes.
    """

    tenant_id = serializers.UUIDField()


class LogoutSerializer(serializers.Serializer):
    """Blacklists a refresh token so it cannot be exchanged again."""

    refresh = serializers.CharField(write_only=True)

    default_error_messages = {  # noqa: RUF012
        "bad_token": _("The token is invalid or has already expired."),
    }

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        self.token = attrs["refresh"]
        return attrs

    def save(self, **kwargs: Any) -> None:
        from rest_framework_simplejwt.exceptions import TokenError

        try:
            RefreshToken(self.token).blacklist()
        except TokenError:
            self.fail("bad_token")
