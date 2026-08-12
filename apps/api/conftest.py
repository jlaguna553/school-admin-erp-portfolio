"""
Pytest fixtures for a schema-per-tenant project.

Two things make this different from a normal Django test suite:

1. **Creating a tenant runs migrations.** ``Client.save()`` triggers
   ``auto_create_schema``, which applies the whole ``TENANT_APPS`` migration set
   inside the new schema. That is slow, so tenants are created **once per
   session** and committed, outside the per-test transaction.

2. **The tenant is chosen by the caller's token, not the host.** One domain
   serves the whole platform, so every client here uses the same host and the
   school is whichever one the signed-in account entered. That is exactly the
   mechanism production uses, which is what makes the isolation tests worth
   anything.

Because credentials are resolved platform-wide before any school is known, a
user who can sign in needs a :class:`PlatformIdentity` and a
:class:`Membership`; ``_make_user`` creates all three so a fixture reads the way
a real account is created.

Two tenants exist so isolation can be *proved* rather than assumed.
"""

from contextlib import contextmanager

import pytest
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

TENANT_A = {"schema": "test_alpha", "name": "Alpha School"}
TENANT_B = {"schema": "test_beta", "name": "Beta School"}

# The one hostname the whole platform is served from.
PLATFORM_HOST = "testserver"

PASSWORD = "Testing!2026pass"


# ---------------------------------------------------------------------------
# Schema setup
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def tenants(django_db_setup, django_db_blocker):
    """Create the public tenant plus two school schemas, once per session."""
    from apps.tenants.models import Client, Domain

    with django_db_blocker.unblock():
        public, _ = Client.objects.get_or_create(
            schema_name="public", defaults={"name": "Platform", "on_trial": False}
        )
        Domain.objects.get_or_create(
            domain="testserver", defaults={"tenant": public, "is_primary": True}
        )

        created = {}
        for key, spec in (("a", TENANT_A), ("b", TENANT_B)):
            tenant = Client.objects.filter(schema_name=spec["schema"]).first()
            if tenant is None:
                tenant = Client(schema_name=spec["schema"], name=spec["name"])
                tenant.save()  # runs the tenant migrations
            # Deliberately no Domain row: schools are not reachable by hostname
            # any more, and giving them one would let a test pass for a reason
            # production does not share.
            created[key] = tenant

        created["public"] = public
        yield created


@pytest.fixture
def tenant_a(tenants, db):
    return tenants["a"]


@pytest.fixture
def tenant_b(tenants, db):
    return tenants["b"]


# ---------------------------------------------------------------------------
# Users. Created inside the tenant's schema, so they are invisible elsewhere.
# ---------------------------------------------------------------------------
def _make_user(schema: str, email: str, role: str, **extra) -> object:
    """A person who can actually sign in: identity, membership and local row.

    The identity is what the login form finds -- there is no host to say which
    school to look in -- and the membership is what lets them through to this
    one. Creating only the school-local row would make an account that exists
    and cannot be used, which no test should be able to depend on.
    """
    from apps.identity.models import Membership, PlatformIdentity
    from apps.identity.services import sync_user_from_identity
    from apps.tenants.models import Client

    user_model = get_user_model()
    first_name = extra.pop("first_name", "Test")
    last_name = extra.pop("last_name", "User")

    if schema == "public":
        # Platform operators are ordinary users of the public schema; there is
        # no membership above the platform itself.
        with schema_context("public"):
            return user_model.objects.create_user(
                email=email,
                password=PASSWORD,
                first_name=first_name,
                last_name=last_name,
                role=role,
                **extra,
            )

    with schema_context("public"):
        identity = PlatformIdentity(
            email=email, first_name=first_name, last_name=last_name, language="es"
        )
        identity.set_password(PASSWORD)
        identity.save()
        membership = Membership.objects.create(
            identity=identity, tenant=Client.objects.get(schema_name=schema), role=role
        )

    with schema_context(schema):
        user = sync_user_from_identity(identity, membership)
        for field, value in extra.items():
            setattr(user, field, value)
        if extra:
            user.save(update_fields=[*extra, "updated_at"])
        return user


@pytest.fixture
def admin_a(tenant_a):
    return _make_user(TENANT_A["schema"], "admin@alpha.test", "school_admin", is_staff=True)


@pytest.fixture
def accountant_a(tenant_a):
    return _make_user(TENANT_A["schema"], "money@alpha.test", "accountant")


@pytest.fixture
def teacher_a(tenant_a):
    return _make_user(TENANT_A["schema"], "teacher@alpha.test", "teacher")


@pytest.fixture
def student_a(tenant_a):
    return _make_user(TENANT_A["schema"], "student@alpha.test", "student")


@pytest.fixture
def coordinator_a(tenant_a):
    return _make_user(TENANT_A["schema"], "coord@alpha.test", "coordinator")


@pytest.fixture
def as_coordinator_a(coordinator_a):
    return _authenticated_as(coordinator_a.email)


@pytest.fixture
def admin_b(tenant_b):
    return _make_user(TENANT_B["schema"], "admin@beta.test", "school_admin", is_staff=True)


# ---------------------------------------------------------------------------
# API clients
# ---------------------------------------------------------------------------
class TenantAPIClient(APIClient):
    """An APIClient on the platform's single host.

    The host argument is kept so call sites read explicitly, but every school is
    served from the same one -- which is the point. A client only reaches a
    school's data once it holds a token naming that school.
    """

    def __init__(self, host: str = PLATFORM_HOST, **kwargs):
        super().__init__(**kwargs)
        self._host = host

    def generic(self, method, path, *args, **kwargs):
        kwargs.setdefault("HTTP_HOST", self._host)
        return super().generic(method, path, *args, **kwargs)


def _login(client: APIClient, email: str) -> str:
    """Obtain a real access token through the login endpoint.

    Deliberately not ``force_authenticate``: the tenant claim is added during
    token issuance, and validating it is the point of several tests.
    """
    response = client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": PASSWORD},
        format="json",
    )
    assert response.status_code == 200, response.data
    return response.data["access"]


def _authenticated_as(email: str) -> "TenantAPIClient":
    """A client of its own, signed in as one person.

    Deliberately not the shared `api_a`. Two fixtures that both set credentials
    on one client leave only the last one signed in, so a test asking for an
    administrator *and* a teacher quietly ran everything as whichever came
    second -- and passed or failed for the wrong reason.
    """
    client = TenantAPIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {_login(TenantAPIClient(), email)}")
    return client


@pytest.fixture
def api_a(tenant_a):
    """An unauthenticated client. Reaches tenant A only once it signs in as one
    of A's people -- the host tells it nothing."""
    return TenantAPIClient()


@pytest.fixture
def api_b(tenant_b):
    return TenantAPIClient()


@pytest.fixture
def api_public(tenants, db):
    return TenantAPIClient()


@pytest.fixture
def as_admin_a(admin_a):
    return _authenticated_as(admin_a.email)


@pytest.fixture
def as_accountant_a(accountant_a):
    return _authenticated_as(accountant_a.email)


@pytest.fixture
def as_teacher_a(teacher_a):
    return _authenticated_as(teacher_a.email)


@pytest.fixture
def as_student_a(student_a):
    return _authenticated_as(student_a.email)


@contextmanager
def tenant_setting(schema: str, **fields):
    """Temporarily change an institution's configuration, then put it back.

    The write has to happen from ``public``: django-tenants refuses to update a
    tenant row from inside another tenant's schema, and by the time a test has
    made one API call the connection is pinned to whichever school served it.
    """
    from apps.tenants.models import Client

    with schema_context("public"):
        client = Client.objects.get(schema_name=schema)
        previous = {name: getattr(client, name) for name in fields}
        for name, value in fields.items():
            setattr(client, name, value)
        client.save(update_fields=[*fields, "updated_at"])
    try:
        yield client
    finally:
        with schema_context("public"):
            for name, value in previous.items():
                setattr(client, name, value)
            client.save(update_fields=[*previous, "updated_at"])


# ---------------------------------------------------------------------------
# Cross-school identity (public schema)
# ---------------------------------------------------------------------------
@pytest.fixture
def identity_ana(tenants):
    """A person with one credential, no schools granted yet."""
    from django_tenants.utils import schema_context as _schema_context

    from apps.identity.models import PlatformIdentity

    with _schema_context("public"):
        identity = PlatformIdentity(
            email="ana@people.test",
            first_name="Ana",
            last_name="Ruiz",
            language="es",
        )
        identity.set_password(PASSWORD)
        identity.save()
        return identity


@pytest.fixture
def grant_membership(tenants):
    """Grant an identity access to a school, in a role."""
    from django_tenants.utils import schema_context as _schema_context

    from apps.identity.models import Membership

    def _grant(identity, tenant, role="school_admin"):
        with _schema_context("public"):
            return Membership.objects.create(identity=identity, tenant=tenant, role=role)

    return _grant


@pytest.fixture
def platform_admin(tenants):
    """A platform operator. Lives in the *public* schema, not in any school."""
    return _make_user(
        "public", "ops@platform.test", "platform_admin", is_staff=True, is_superuser=True
    )


@pytest.fixture
def as_platform(platform_admin):
    return _authenticated_as(platform_admin.email)


@pytest.fixture
def token_a(api_a, admin_a) -> str:
    """A raw access token issued by tenant A, for cross-tenant replay tests."""
    return _login(api_a, admin_a.email)


# ---------------------------------------------------------------------------
# Academic / billing data inside tenant A
# ---------------------------------------------------------------------------
@pytest.fixture
def academic_year_a(tenant_a):
    from datetime import date

    from apps.academic.models import AcademicYear

    with schema_context(TENANT_A["schema"]):
        return AcademicYear.objects.create(
            name="2026-2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 6, 30),
            is_current=True,
        )


@pytest.fixture
def program_a(tenant_a):
    from apps.academic.models import Program

    with schema_context(TENANT_A["schema"]):
        return Program.objects.create(
            code="PRI", name_es="Educación Primaria", name_en="Primary Education"
        )


@pytest.fixture
def term_a(tenant_a, academic_year_a):
    from datetime import date

    from apps.academic.models import Term

    with schema_context(TENANT_A["schema"]):
        return Term.objects.create(
            academic_year=academic_year_a,
            name="Primer trimestre",
            ordinal=1,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 15),
            is_current=True,
        )


@pytest.fixture
def subject_a(tenant_a, program_a, teacher_a):
    from apps.academic.models import Subject

    with schema_context(TENANT_A["schema"]):
        return Subject.objects.create(
            code="MAT", name="Matemáticas", program=program_a, credits=6, teacher=teacher_a
        )


@pytest.fixture
def group_a(tenant_a, program_a, academic_year_a, teacher_a):
    from apps.academic.models import StudentGroup

    with schema_context(TENANT_A["schema"]):
        return StudentGroup.objects.create(
            name="A",
            program=program_a,
            academic_year=academic_year_a,
            tutor=teacher_a,
            room="Aula 1",
        )


@pytest.fixture
def enrollment_a(tenant_a, student_a, program_a, academic_year_a, group_a):
    from apps.academic.models import Enrollment, EnrollmentStatus

    with schema_context(TENANT_A["schema"]):
        return Enrollment.objects.create(
            student=student_a,
            program=program_a,
            academic_year=academic_year_a,
            group=group_a,
            status=EnrollmentStatus.ACTIVE,
            enrolled_on=academic_year_a.start_date,
        )


@pytest.fixture
def slot_a(tenant_a, group_a, subject_a):
    """A Monday class, so tests can pick any Monday and the weekday matches."""
    from datetime import time

    from apps.academic.models import TimetableSlot, Weekday

    with schema_context(TENANT_A["schema"]):
        return TimetableSlot.objects.create(
            group=group_a,
            subject=subject_a,
            weekday=Weekday.MONDAY,
            start_time=time(8, 0),
            end_time=time(9, 0),
            room="Aula 1",
        )
