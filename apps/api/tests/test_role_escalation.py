"""
Role assignment must not be a way out of your own tenant.

``platform_admin`` is the only role that means anything above an institution:
it is what :class:`apps.core.permissions.IsPlatformAdmin` looks for, and it is
checked in the public schema. The users endpoint lets school staff set the
``role`` field, so without an explicit guard a school administrator could grant
that role -- to a colleague or to themselves -- and the write would succeed.
"""

import pytest
from django_tenants.utils import schema_context

from conftest import TENANT_A

pytestmark = pytest.mark.django_db


class TestPlatformRoleIsNotGrantable:
    def test_school_admin_cannot_create_a_platform_admin(self, as_admin_a):
        response = as_admin_a.post(
            "/api/v1/users/",
            {
                "email": "sneaky@alpha.test",
                "first_name": "Sneaky",
                "last_name": "User",
                "role": "platform_admin",
                "password": "Escalate!2026pass",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "role" in response.data["error"]["details"]

        from apps.users.models import User

        with pytest.raises(User.DoesNotExist):
            User.all_objects.get(email="sneaky@alpha.test")

    def test_school_admin_cannot_promote_themselves(self, as_admin_a, admin_a):
        """Refused before the role is even read.

        This used to be a 400 from the role validator. It is now a 403 from the
        rank check, because nobody outranks themselves -- so the administration
        endpoint refuses to act on your own record whatever you were asking for.
        Self-service lives at `me/`, where `role` is read-only.
        """
        response = as_admin_a.patch(
            f"/api/v1/users/{admin_a.id}/",
            {"role": "platform_admin"},
            format="json",
        )

        assert response.status_code == 403
        with schema_context(TENANT_A["schema"]):
            admin_a.refresh_from_db()
        assert admin_a.role == "school_admin"

    def test_school_admin_cannot_promote_a_teacher(self, as_admin_a, teacher_a):
        response = as_admin_a.patch(
            f"/api/v1/users/{teacher_a.id}/",
            {"role": "platform_admin"},
            format="json",
        )

        assert response.status_code == 400
        with schema_context(TENANT_A["schema"]):
            teacher_a.refresh_from_db()
        assert teacher_a.role == "teacher"

    def test_platform_admin_cannot_plant_the_role_inside_a_school(self, as_platform, tenant_a):
        """Even the operator is refused -- in a school's schema the role is meaningless.

        Platform staff exist in ``public``; a row carrying ``platform_admin``
        inside a school would look like an escalation to any reader and confer
        nothing, so the same validator applies on the platform endpoint.
        """
        response = as_platform.post(
            f"/api/v1/tenants/{tenant_a.id}/users/",
            {
                "email": "planted@alpha.test",
                "first_name": "Planted",
                "last_name": "Admin",
                "role": "platform_admin",
                "password": "Planted!2026pass",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "role" in response.data["error"]["details"]


class TestOrdinaryRolesStillWork:
    def test_school_admin_can_still_grant_school_roles(self, as_admin_a, teacher_a):
        response = as_admin_a.patch(
            f"/api/v1/users/{teacher_a.id}/",
            {"role": "coordinator"},
            format="json",
        )

        assert response.status_code == 200, response.data
        with schema_context(TENANT_A["schema"]):
            teacher_a.refresh_from_db()
        assert teacher_a.role == "coordinator"

    def test_a_platform_admin_can_be_created_in_the_public_schema(self, tenants):
        """The role is not unusable -- it is only unavailable from a school."""
        from django_tenants.utils import schema_context

        from apps.users.serializers import UserCreateSerializer

        with schema_context("public"):
            serializer = UserCreateSerializer(
                data={
                    "email": "second.ops@platform.test",
                    "first_name": "Second",
                    "last_name": "Ops",
                    "role": "platform_admin",
                    "password": "Platform!2026pass",
                }
            )
            assert serializer.is_valid(), serializer.errors

    def test_two_independent_rules_guard_the_role(self, tenants):
        """Context and rank, checked separately, on purpose.

        Either alone leaves a hole: rank would let an operator plant
        `platform_admin` inside a school, where it means nothing; context alone
        would let a school administrator appoint another one.
        """
        from django_tenants.utils import schema_context

        from apps.core.roles import assignable_roles
        from apps.users.serializers import UserSerializer

        # Context: not a role a school has, whoever is asking.
        with schema_context(TENANT_A["schema"]):
            serializer = UserSerializer(data={"role": "platform_admin"}, partial=True)
            serializer.is_valid()
            assert "role" in serializer.errors

        # Rank: a school administrator may appoint below themselves only.
        allowed = assignable_roles("school_admin")
        assert "coordinator" in allowed
        assert "school_admin" not in allowed
        assert "platform_admin" not in allowed
