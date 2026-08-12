"""
The platform operator's cross-institution surface.

Everything here is served on the *public* host, which is a different URLconf
from the school hosts. Two properties matter and are asserted rather than
assumed: only platform staff can reach it, and a request that reads one
school's users must leave the connection pointing back at ``public`` when it
finishes -- otherwise the next request served by the same worker would silently
read the wrong school's data.
"""

import pytest
from django.db import connection
from django_tenants.utils import schema_context

from conftest import PASSWORD, TENANT_A, TENANT_B

pytestmark = pytest.mark.django_db


def _users_url(tenant) -> str:
    return f"/api/v1/tenants/{tenant.id}/users/"


class TestAccess:
    def test_school_admin_cannot_reach_the_platform_users_api(self, api_a, admin_a, tenant_b):
        """A school administrator is staff *inside their school* -- not on the platform."""
        response = api_a.post(
            "/api/v1/auth/login/",
            {"email": admin_a.email, "password": PASSWORD},
            format="json",
        )
        token = response.data["access"]

        # Replayed against the platform host, where the route actually lives.
        from conftest import TenantAPIClient

        public = TenantAPIClient("testserver")
        public.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        assert public.get(_users_url(tenant_b)).status_code in (401, 403)

    def test_anonymous_is_rejected(self, api_public, tenant_a):
        assert api_public.get(_users_url(tenant_a)).status_code == 401

    def test_platform_admin_lists_a_school_users(self, as_platform, tenant_a, admin_a):
        response = as_platform.get(_users_url(tenant_a))

        assert response.status_code == 200
        emails = [row["email"] for row in response.data["results"]]
        assert admin_a.email in emails

    def test_each_school_is_listed_separately(self, as_platform, tenant_a, tenant_b, admin_a):
        """The same endpoint returns different people depending on the school in the URL."""
        in_a = as_platform.get(_users_url(tenant_a)).data["results"]
        in_b = as_platform.get(_users_url(tenant_b)).data["results"]

        assert admin_a.email in [row["email"] for row in in_a]
        assert admin_a.email not in [row["email"] for row in in_b]


class TestProvisioning:
    """Opening a school should ask for nothing an operator has to invent."""

    def test_a_name_is_enough(self, as_platform):
        response = as_platform.post(
            "/api/v1/tenants/",
            {"name": "Instituto Ñandú", "default_currency": "MXN"},
            format="json",
        )

        assert response.status_code == 201, response.data
        # Derived, not asked for: the schema is how the data is isolated, not a
        # decision worth putting in front of someone opening a school.
        assert response.data["schema_name"] == "instituto_nandu"
        # And the id comes back, so the console can open the new school and add
        # its first administrator without a second lookup.
        assert response.data["id"]

    def test_two_schools_may_share_a_name(self, as_platform):
        """The second is provisioned rather than rejected on a name clash."""
        first = as_platform.post("/api/v1/tenants/", {"name": "San José"}, format="json")
        second = as_platform.post("/api/v1/tenants/", {"name": "San José"}, format="json")

        assert first.data["schema_name"] == "san_jose"
        assert second.data["schema_name"] == "san_jose_2"

    def test_a_reserved_name_does_not_collide_with_the_platform(self, as_platform):
        response = as_platform.post("/api/v1/tenants/", {"name": "public"}, format="json")

        assert response.status_code == 201
        assert response.data["schema_name"] != "public"

    def test_no_hostname_is_involved(self, as_platform):
        """A school is not reached at an address of its own any more."""
        response = as_platform.post("/api/v1/tenants/", {"name": "Sin Dominio"}, format="json")

        assert response.status_code == 201
        assert response.data["domains"] == []


class TestSchemaRestoration:
    def test_the_connection_returns_to_public_after_a_request(self, as_platform, tenant_a, admin_a):
        """The schema switch must not outlive the request that needed it.

        Workers are reused, so a connection left pointing at a school would make
        the *next* caller read that school's tables.
        """
        as_platform.get(_users_url(tenant_a))

        assert connection.schema_name == "public"

    def test_the_connection_returns_to_public_after_a_failed_request(self, as_platform, tenant_a):
        missing = "00000000-0000-0000-0000-000000000000"
        response = as_platform.get(f"/api/v1/tenants/{tenant_a.id}/users/{missing}/")

        assert response.status_code == 404
        assert connection.schema_name == "public"


class TestManagingSchoolUsers:
    def test_creates_a_user_inside_the_target_school(self, as_platform, tenant_a):
        response = as_platform.post(
            _users_url(tenant_a),
            {
                "email": "new.head@alpha.test",
                "first_name": "New",
                "last_name": "Head",
                "role": "school_admin",
                "password": "Provision!2026pass",
            },
            format="json",
        )

        assert response.status_code == 201, response.data

        from apps.users.models import User

        with schema_context(TENANT_A["schema"]):
            assert User.objects.filter(email="new.head@alpha.test").exists()
        with schema_context(TENANT_B["schema"]):
            assert not User.objects.filter(email="new.head@alpha.test").exists()

    def test_grants_a_role_to_an_existing_user(self, as_platform, tenant_a, teacher_a):
        response = as_platform.patch(
            f"{_users_url(tenant_a)}{teacher_a.id}/",
            {"role": "coordinator"},
            format="json",
        )

        assert response.status_code == 200, response.data
        with schema_context(TENANT_A["schema"]):
            teacher_a.refresh_from_db()
        assert teacher_a.role == "coordinator"

    def test_deactivating_a_user_is_a_soft_delete(self, as_platform, tenant_a, teacher_a):
        response = as_platform.delete(f"{_users_url(tenant_a)}{teacher_a.id}/")

        assert response.status_code == 204

        from apps.users.models import User

        with schema_context(TENANT_A["schema"]):
            # Still there -- rule A.3. Only the default manager hides it.
            assert User.all_objects.filter(pk=teacher_a.pk).exists()
            assert not User.objects.filter(pk=teacher_a.pk).exists()

    def test_an_inactive_institution_is_not_addressable(self, as_platform, tenant_b):
        tenant_b.delete()  # soft: deactivates, keeps the schema
        try:
            assert as_platform.get(_users_url(tenant_b)).status_code == 404
        finally:
            tenant_b.restore()
