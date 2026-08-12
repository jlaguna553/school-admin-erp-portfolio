"""
Selecting a school from a token, outside the DRF authentication path.

The refresh and logout endpoints take no access token -- they read the refresh
token from an httpOnly cookie -- so they never pass through
:class:`TenantJWTAuthentication`, and would otherwise run on ``public``.

They cannot. SimpleJWT records every issued refresh token in ``OutstandingToken``
with a ForeignKey to the user, and users live inside their school's schema; a
record written on ``public`` for a school's user violates that key outright.
Blacklisting has the same shape in reverse: a token revoked in the wrong schema
is not revoked at all, and the next refresh would happily accept it.

So the schema is taken from the token's own ``tenant_schema`` claim -- after its
signature is verified, never before.
"""

from django.db import connection
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import UntypedToken


def activate_schema_from_token(raw_token: str) -> str | None:
    """Point the connection at the school named by a signed token.

    ``UntypedToken`` verifies the signature and expiry but does **not** consult
    the blacklist -- which is exactly what is wanted here, because the blacklist
    can only be read once the schema is known. The full check happens afterwards,
    in the right schema.

    Returns the schema activated, or ``None`` when the token names no school or
    cannot be trusted. Callers treat ``None`` as "stay on public"; an invalid
    token then fails its real validation a moment later.
    """
    from apps.tenants.models import Client

    try:
        token = UntypedToken(raw_token)
    except TokenError:
        return None

    schema = token.get("tenant_schema")
    if not schema or schema == "public":
        return None

    tenant = Client.objects.filter(schema_name=schema, is_active=True).first()
    if tenant is None:
        return None

    connection.set_tenant(tenant)
    return schema
