"""Tenant-aware JWT authentication.

One hostname serves every school, so nothing about the request itself says which
institution it is for. The access token does: it carries a ``tenant_schema``
claim, signed by us, and this class is where that claim becomes a Postgres
``search_path``.

Two things are checked, and the second is the one that matters.

The claim is *authentic* -- it is signed, so a caller cannot invent a schema
name. But authenticity is not authorisation: a token issued last week still says
what it said then, and access can be revoked in between. So after the schema is
selected and the user loaded, the membership is re-read from the database. A
token naming a school the holder no longer works at is refused, which is why
revoking access takes effect on the next request rather than whenever the token
happens to expire.
"""

from typing import Any

from django.db import connection
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.exceptions import TenantMismatch


class TenantJWTAuthentication(JWTAuthentication):
    """Selects the school named by the token, then verifies it is still allowed."""

    def get_user(self, validated_token: Any) -> Any:
        schema = validated_token.get("tenant_schema")

        if not schema or schema == "public":
            # Platform operators work above every institution; their accounts
            # live in the public schema, which is where the request already is.
            return super().get_user(validated_token)

        tenant = self._activate(schema)
        user = super().get_user(validated_token)

        if not self._may_act_here(user, tenant):
            raise TenantMismatch()

        return user

    @staticmethod
    def _activate(schema: str) -> Any:
        """Point the connection at the named school.

        Reads the row rather than trusting the claim's spelling: a schema that
        has been deactivated, or never existed, must not be selectable at all.
        """
        from apps.tenants.models import Client

        tenant = Client.objects.filter(schema_name=schema, is_active=True).first()
        if tenant is None:
            raise TenantMismatch()

        connection.set_tenant(tenant)
        return tenant

    @staticmethod
    def _may_act_here(user: Any, tenant: Any) -> bool:
        """Is this person still a member of this school?

        Checked on every request, deliberately. The alternative -- trusting the
        token until it expires -- would leave someone working inside a school
        for the remaining life of an access token after their access was
        revoked.
        """
        from apps.identity.models import Membership

        identity_id = getattr(user, "identity_id", None)
        if not identity_id:
            # An account local to this school, with no platform credential. It
            # was loaded from this school's own table, so its presence is the
            # membership.
            return True

        return Membership.objects.filter(
            identity_id=identity_id,
            tenant=tenant,
            is_active=True,
        ).exists()
