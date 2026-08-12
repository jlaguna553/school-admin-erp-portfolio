"""
Tenant isolation tests.

These are the highest-value tests in the project: a leak here means one school
can read another school's students.

The mechanism they exercise changed with the move to a single domain, and it is
worth being precise about how. Isolation is still schema-per-tenant -- each
school's rows live in their own Postgres schema and no query carries a
``tenant_id`` filter. What changed is *selection*: the hostname used to name the
schema, and now the access token does.

That makes the token load-bearing in a way it was not before, so these tests
concentrate on the two questions that follow from it. Can a signed claim reach a
school its holder is not a member of? And does a request leave the connection
where it found it?
"""

import pytest
from django.db import connection
from django_tenants.utils import schema_context

from conftest import PASSWORD, TENANT_A, TENANT_B, TenantAPIClient

pytestmark = pytest.mark.django_db


def _login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")


class TestSchemaSelection:
    def test_the_host_says_nothing_about_the_school(self, api_a, api_b):
        """One domain: an unauthenticated request is on ``public``, always."""
        assert api_a.get("/api/health/").data["schema"] == "public"
        assert api_b.get("/api/health/").data["schema"] == "public"

    def test_signing_in_selects_the_school(self, api_a, admin_a):
        response = _login(api_a, admin_a.email)

        assert response.status_code == 200
        assert response.data["tenant"]["schema"] == TENANT_A["schema"]
        assert response.data["user"]["role"] == "school_admin"

    def test_the_connection_returns_to_public_after_a_request(self, as_admin_a):
        """Connections are reused; a leaked schema would serve the next caller.

        This is the property the hostname used to provide for free, because it
        was re-read on every request. Selecting from a token means something has
        to actively put the connection back.
        """
        as_admin_a.get("/api/v1/users/")

        assert connection.schema_name == "public"

    def test_it_returns_to_public_even_when_the_view_fails(self, as_admin_a):
        as_admin_a.get("/api/v1/users/00000000-0000-0000-0000-000000000000/")

        assert connection.schema_name == "public"


class TestUserIsolation:
    def test_users_are_not_visible_across_tenants(self, as_admin_a, admin_b):
        """Tenant B's admin must not appear in tenant A's user list."""
        response = as_admin_a.get("/api/v1/users/")
        assert response.status_code == 200

        emails = {row["email"] for row in response.data["results"]}
        assert "admin@alpha.test" in emails
        assert admin_b.email not in emails

    def test_an_email_now_identifies_one_person_platform_wide(self, api_a, admin_a, admin_b):
        """The one guarantee the single domain took away, pinned deliberately.

        Two schools used to be able to hold their own ``ana@example.com``,
        because the hostname disambiguated them at login. There is no
        disambiguator any more, so the address has to identify one person -- and
        the API says so rather than creating an account nobody could sign in to.
        """
        token = _login(api_a, admin_a.email).data["access"]
        api_a.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_a.post(
            "/api/v1/users/",
            {
                "email": "admin@beta.test",  # already a person at the other school
                "first_name": "Impostor",
                "last_name": "Account",
                "role": "teacher",
                "language": "es",
                "password": "Collide!2026pass",
            },
            format="json",
        )

        assert response.status_code == 400
        # The message must not reveal that the address exists *elsewhere*.
        detail = str(response.data["error"]["details"]["email"])
        assert "beta" not in detail.lower()
        assert "institution" not in detail.lower()

    def test_academic_data_does_not_cross_schemas(self, program_a, tenant_b):
        from apps.academic.models import Program

        with schema_context(TENANT_B["schema"]):
            assert not Program.objects.filter(code=program_a.code).exists()


class TestTokenTenantBinding:
    """A signed claim is authentic. It is not, by itself, authorisation."""

    def test_a_claim_for_a_revoked_school_is_refused(
        self, api_a, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        """The case the membership check exists for.

        Ana has signed in at both schools, so a row of hers exists in each. Her
        access to B is then revoked, and a token of hers is re-pointed at B and
        re-signed with the server's own key -- the strongest position someone
        holding a valid session can reach.

        Without the check the request would succeed: the schema is real, the
        signature is ours, and a user with that id genuinely exists there. Only
        re-reading the membership refuses it.
        """
        from rest_framework_simplejwt.tokens import AccessToken

        grant_membership(identity_ana, tenant_a)
        membership_b = grant_membership(identity_ana, tenant_b)

        at_a = _login(api_a, identity_ana.email)
        token = AccessToken(at_a.data["access"])
        user_id = at_a.data["user"]["id"]

        # Sign in at B too, so the row is there and the id lines up.
        switched = api_a.post(
            "/api/v1/auth/switch/",
            {"tenant_id": str(tenant_b.id)},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {at_a.data['access']}",
        )
        assert switched.status_code == 200

        with schema_context("public"):
            membership_b.delete()  # soft

        token["tenant_schema"] = TENANT_B["schema"]
        token["tenant_id"] = str(tenant_b.id)
        token["user_id"] = switched.data["user"]["id"]
        assert switched.data["user"]["id"] != user_id  # different row, same person

        client = TenantAPIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token!s}")
        response = client.get("/api/v1/users/")

        assert response.status_code == 403
        assert response.data["error"]["code"] == "tenant_mismatch"

    def test_revoking_membership_takes_effect_on_the_next_request(
        self, api_a, identity_ana, grant_membership, tenant_a
    ):
        """Not when the token expires -- which could be another hour."""
        membership = grant_membership(identity_ana, tenant_a)
        token = _login(api_a, identity_ana.email).data["access"]
        api_a.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        assert api_a.get("/api/v1/users/").status_code == 200

        with schema_context("public"):
            membership.delete()  # soft

        assert api_a.get("/api/v1/users/").status_code == 403

    def test_a_claim_naming_an_unknown_schema_is_refused(self, api_a, admin_a):
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken(_login(api_a, admin_a.email).data["access"])
        token["tenant_schema"] = "no_such_school"

        client = TenantAPIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token!s}")

        assert client.get("/api/v1/users/").status_code == 403

    def test_a_claim_for_a_school_with_no_row_of_yours_is_refused(self, api_a, admin_a, tenant_b):
        """Rejected before membership is even consulted: there is nobody to load.

        401 rather than 403 because authentication itself fails -- the user id in
        the token names no row in that schema. Worth pinning so the weaker
        outcome is not mistaken for the membership check doing its job.
        """
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken(_login(api_a, admin_a.email).data["access"])
        token["tenant_schema"] = TENANT_B["schema"]
        token["tenant_id"] = str(tenant_b.id)

        client = TenantAPIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token!s}")

        assert client.get("/api/v1/users/").status_code == 401

    def test_a_school_token_cannot_reach_the_platform_api(self, api_a, admin_a):
        """Both surfaces share a host now; the permission is what separates them."""
        token = _login(api_a, admin_a.email).data["access"]
        api_a.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        assert api_a.get("/api/v1/tenants/").status_code in (401, 403)

    def test_unauthenticated_requests_are_rejected(self, api_a):
        assert api_a.get("/api/v1/users/").status_code == 401
