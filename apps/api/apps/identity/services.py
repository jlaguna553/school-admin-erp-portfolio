"""
Signing in when one hostname serves every school.

The host used to say which institution a request was for, which meant the login
form could look up credentials in that school's own table. With a single domain
there is no such hint at the moment someone types their password, so credentials
have to be findable without knowing the school first -- which is why they live
once in :class:`PlatformIdentity`, in the public schema, and membership of each
school is a separate fact.

This module is the only place that turns "an email and a password" into "a
person, and the school they are about to work in".
"""

from typing import Any

from django.db import connection
from django.utils.translation import gettext_lazy as _

from apps.core import modules
from apps.core.exceptions import BusinessRuleViolation
from apps.tenants.models import Client
from apps.users.models import User

from .models import Membership, PlatformIdentity


class NoSchoolAccess(BusinessRuleViolation):
    """Valid credentials, but the person is not a member of any active school."""

    status_code = 403
    default_detail = _("This account is not registered at any active institution.")
    default_code = "no_school_access"


def authenticate_identity(email: str, password: str) -> PlatformIdentity | None:
    """Verify credentials against the platform-wide identity.

    Returns ``None`` for both "no such person" and "wrong password", on purpose:
    the two are indistinguishable to a caller, so the login form cannot be used
    to discover which email addresses exist.
    """
    if not email or not password:
        return None

    identity = PlatformIdentity.objects.filter(
        email__iexact=email.strip().lower(), is_active=True
    ).first()
    if identity is None or not identity.check_password(password):
        return None

    return identity


def memberships_for(identity: PlatformIdentity) -> list[Membership]:
    """Every school this person may currently work at."""
    return list(identity.schools())


def entry_order(identity: PlatformIdentity, memberships: list[Membership]) -> list[Membership]:
    """The schools to try opening, best first.

    The one they used last, when that access still stands, then the rest by
    name. Someone with a single school never notices this exists, and someone
    with several lands where they left off instead of somewhere arbitrary.
    """
    if identity.last_tenant_id is None:
        return list(memberships)

    remembered = [m for m in memberships if m.tenant_id == identity.last_tenant_id]
    others = [m for m in memberships if m.tenant_id != identity.last_tenant_id]
    return remembered + others


def open_first_available(
    identity: PlatformIdentity, memberships: list[Membership]
) -> tuple[Membership, Any]:
    """Enter the best school that will actually have them.

    Tried in order rather than committing to the first, because a membership is
    only half of the answer: the school can also have deactivated the account,
    and that refusal is honoured. Someone deactivated at one of their two
    schools should still be able to work at the other -- an earlier version
    stopped at the remembered school and locked them out of both.
    """
    for membership in entry_order(identity, memberships):
        connection.set_tenant(membership.tenant)
        user = sync_user_from_identity(identity, membership)
        if user is not None:
            return membership, user

    connection.set_schema_to_public()
    raise NoSchoolAccess()


def remember_entry(identity: PlatformIdentity, membership: Membership) -> None:
    if identity.last_tenant_id != membership.tenant_id:
        identity.last_tenant_id = membership.tenant_id
        identity.save(update_fields=["last_tenant", "updated_at"])


def sync_user_from_identity(identity: PlatformIdentity, membership: Membership) -> Any:
    """Return the school-local row for this identity, or ``None`` if barred here.

    The row has to exist: enrollments point at a student, invoices record who
    issued them, and permissions are per-schema. Creating it lazily at first
    login rather than when the membership is granted means the schema is only
    written to by someone who actually turned up.

    Profile fields are copied from the identity every time, so a name or
    language corrected once is corrected everywhere. The password column is left
    unusable -- the credential lives in the public schema and nowhere else, which
    is the whole point; a copy here would be a second password able to drift.

    Two parties can say no, and both are honoured. The platform withholds a
    membership; the school deactivates the account. An earlier version of this
    reactivated the local row on every login, on the grounds that the membership
    was authoritative -- which meant a school administrator could deactivate
    someone and watch them sign in again minutes later, with nothing in the
    interface to explain it. The more restrictive answer wins instead.
    """
    user = User.all_objects.filter(identity_id=identity.id).first()
    if user is None:
        # An account may already exist at this school under the same email --
        # someone hired locally first, granted platform access later. Adopt it
        # rather than colliding with its unique email.
        user = User.all_objects.filter(email__iexact=identity.email).first()

    if user is not None and (not user.is_active or user.deleted_at is not None):
        return None

    if user is None:
        user = User(email=identity.email)
        user.set_unusable_password()

    user.identity_id = identity.id
    user.first_name = identity.first_name
    user.last_name = identity.last_name
    user.phone = identity.phone
    user.language = identity.language
    user.role = membership.role
    # `is_staff` follows the role, as it does for locally created staff.
    user.is_staff = membership.role in {"school_admin", "coordinator"}
    user.save()
    return user


def enter_school(identity: PlatformIdentity, membership: Membership) -> Any:
    """Select one named school and return the person's row inside it.

    Used when the school is already decided -- switching, or provisioning --
    unlike :func:`open_first_available`, which is signing in and may fall
    through.
    """
    connection.set_tenant(membership.tenant)
    user = sync_user_from_identity(identity, membership)
    if user is None:
        # Deactivated at this school. The platform is willing, the school is
        # not, and the more restrictive answer wins.
        raise NoSchoolAccess()
    return user


def provision_school_member(*, password: str, role: str, email: str, **profile: Any) -> User:
    """Create a person, grant them this school, and make their local row.

    Called from a school's own users screen, where the connection is already
    pinned to that school. The identity and membership have to be written on
    ``public``, so the schema is switched for those two writes and put back --
    a school-local row is created on the way out, inside the school again.

    Written as one transaction on purpose: an identity with no membership is an
    account that can sign in nowhere, and a membership with no local row is one
    that cannot be seen in the school's list. Neither half is useful alone.
    """
    from django.db import transaction
    from django_tenants.utils import schema_context

    tenant_schema = connection.schema_name

    with transaction.atomic(), schema_context("public"):
        tenant = Client.objects.get(schema_name=tenant_schema)
        identity = PlatformIdentity(email=email, **profile)
        identity.set_password(password)
        identity.save()
        membership = Membership.objects.create(identity=identity, tenant=tenant, role=role)

    connection.set_tenant(tenant)
    user = sync_user_from_identity(identity, membership)
    if user is None:  # pragma: no cover -- the row was just created
        raise NoSchoolAccess()
    return user


def membership_for_tenant(identity: PlatformIdentity, tenant_id: Any) -> Membership | None:
    """The membership granting access to one specific school, if any."""
    return (
        Membership.objects.filter(
            identity=identity, tenant_id=tenant_id, is_active=True, tenant__is_active=True
        )
        .select_related("tenant")
        .first()
    )


def school_payload(membership: Membership, current_schema: str) -> dict[str, Any]:
    """One entry of the school list the client renders in its switcher."""
    tenant: Client = membership.tenant
    return {
        "tenant_id": str(tenant.id),
        "name": tenant.name,
        "schema": tenant.schema_name,
        "role": membership.role,
        "default_currency": tenant.default_currency,
        "brand_color": tenant.brand_color,
        "modules": modules.enabled_modules(tenant.disabled_modules),
        "is_current": tenant.schema_name == current_schema,
    }
