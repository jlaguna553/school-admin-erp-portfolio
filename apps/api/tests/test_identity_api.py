"""
The operator's view of people and where they work.

There used to be a second line of defence here: these routes lived in a separate
URLconf served only on the platform's hostname, so a school's host returned 404
before any permission was consulted. One domain removes that, and
``IsPlatformAdmin`` is now the whole of it -- which is why the access tests below
matter more than they did.

The membership list is the sensitive part: it says which schools employ a given
person, and no school is entitled to read that about another.
"""

import pytest
from django_tenants.utils import schema_context

from conftest import PASSWORD

pytestmark = pytest.mark.django_db

IDENTITIES = "/api/v1/identities/"


class TestAccess:
    def test_a_school_admin_cannot_reach_it(self, api_a, admin_a):
        """The permission is the only thing separating the two surfaces now."""
        token = api_a.post(
            "/api/v1/auth/login/",
            {"email": admin_a.email, "password": PASSWORD},
            format="json",
        ).data["access"]
        api_a.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        assert api_a.get(IDENTITIES).status_code in (401, 403)

    def test_anonymous_is_rejected(self, api_public):
        assert api_public.get(IDENTITIES).status_code == 401

    def test_a_school_session_cannot_list_people(self, as_admin_a):
        """Signed in, and still refused: being staff somewhere is not being an
        operator."""
        assert as_admin_a.get(IDENTITIES).status_code in (401, 403)


class TestManagingPeople:
    def test_creates_a_person_with_one_credential(self, as_platform):
        response = as_platform.post(
            IDENTITIES,
            {
                "email": "Nueva.Persona@people.test",
                "first_name": "Nueva",
                "last_name": "Persona",
                "language": "es",
                "password": "Identity!2026pass",
            },
            format="json",
        )

        assert response.status_code == 201, response.data

        from apps.identity.models import PlatformIdentity

        with schema_context("public"):
            identity = PlatformIdentity.objects.get(email="nueva.persona@people.test")
            # Never stored raw, and never as the value that was sent.
            assert identity.password != "Identity!2026pass"
            assert identity.check_password("Identity!2026pass")

    def test_a_weak_password_is_refused(self, as_platform):
        response = as_platform.post(
            IDENTITIES,
            {
                "email": "weak@people.test",
                "first_name": "W",
                "last_name": "K",
                "language": "es",
                "password": "1234",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "password" in response.data["error"]["details"]

    def test_lists_a_person_with_their_schools(
        self, as_platform, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        grant_membership(identity_ana, tenant_a, role="school_admin")
        grant_membership(identity_ana, tenant_b, role="teacher")

        response = as_platform.get(f"{IDENTITIES}{identity_ana.id}/")

        assert response.status_code == 200
        roles = {m["tenant_schema"]: m["role"] for m in response.data["memberships"]}
        assert roles == {"test_alpha": "school_admin", "test_beta": "teacher"}

    def test_resets_a_password_for_every_school_at_once(
        self, as_platform, api_a, identity_ana, grant_membership, tenant_a
    ):
        grant_membership(identity_ana, tenant_a)

        response = as_platform.post(
            f"{IDENTITIES}{identity_ana.id}/set-password/",
            {"new_password": "Recovered!2026pass"},
            format="json",
        )

        assert response.status_code == 204
        login = api_a.post(
            "/api/v1/auth/login/",
            {"email": identity_ana.email, "password": "Recovered!2026pass"},
            format="json",
        )
        assert login.status_code == 200


class TestManagingMemberships:
    def test_grants_access_to_a_school(self, as_platform, identity_ana, tenant_a):
        response = as_platform.post(
            f"{IDENTITIES}{identity_ana.id}/memberships/",
            {"tenant": str(tenant_a.id), "role": "coordinator"},
            format="json",
        )

        assert response.status_code == 201, response.data
        assert response.data["role"] == "coordinator"
        assert response.data["tenant_schema"] == "test_alpha"

    def test_platform_admin_is_not_a_school_membership(self, as_platform, identity_ana, tenant_a):
        """It is authority *above* every school, not a role inside one."""
        response = as_platform.post(
            f"{IDENTITIES}{identity_ana.id}/memberships/",
            {"tenant": str(tenant_a.id), "role": "platform_admin"},
            format="json",
        )

        assert response.status_code == 400
        assert "role" in response.data["error"]["details"]

    def test_granting_the_same_school_twice_updates_the_role(
        self, as_platform, identity_ana, tenant_a
    ):
        """Rather than colliding with the uniqueness constraint."""
        first = as_platform.post(
            f"{IDENTITIES}{identity_ana.id}/memberships/",
            {"tenant": str(tenant_a.id), "role": "teacher"},
            format="json",
        )
        second = as_platform.post(
            f"{IDENTITIES}{identity_ana.id}/memberships/",
            {"tenant": str(tenant_a.id), "role": "school_admin"},
            format="json",
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert second.data["id"] == first.data["id"]
        assert second.data["role"] == "school_admin"

    def test_re_granting_a_revoked_school_reactivates_it(
        self, as_platform, api_a, identity_ana, grant_membership, tenant_a
    ):
        membership = grant_membership(identity_ana, tenant_a)
        as_platform.delete(f"{IDENTITIES}{identity_ana.id}/memberships/{membership.id}/")
        assert self._can_sign_in(api_a, identity_ana) is False

        response = as_platform.post(
            f"{IDENTITIES}{identity_ana.id}/memberships/",
            {"tenant": str(tenant_a.id), "role": "school_admin"},
            format="json",
        )

        assert response.status_code == 201
        assert self._can_sign_in(api_a, identity_ana) is True

    def test_revoking_keeps_the_school_local_row(
        self, as_platform, api_a, identity_ana, grant_membership, tenant_a
    ):
        """The invoices they issued still name them."""
        from apps.users.models import User

        membership = grant_membership(identity_ana, tenant_a)
        self._can_sign_in(api_a, identity_ana)  # creates the local row

        response = as_platform.delete(f"{IDENTITIES}{identity_ana.id}/memberships/{membership.id}/")

        assert response.status_code == 204
        with schema_context("test_alpha"):
            assert User.all_objects.filter(email=identity_ana.email).exists()

    @staticmethod
    def _can_sign_in(client, identity) -> bool:
        response = client.post(
            "/api/v1/auth/login/",
            {"email": identity.email, "password": PASSWORD},
            format="json",
        )
        return response.status_code == 200
