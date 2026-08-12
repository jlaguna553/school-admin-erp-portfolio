"""
One person, one password, several schools.

The rest of the ERP is schema-per-tenant, so the same person at two schools was
two unrelated rows with two passwords. These tests pin down the properties that
make a single credential safe:

* the password is checked once, in the public schema;
* access to a given school is a separate, explicit fact;
* signing in opens exactly one school, and moving between them is a switch
  rather than a second sign-in.

With one hostname for the whole platform, every client below uses the same host.
Which school a request reaches is decided by the token it carries -- which is
the mechanism production uses, and the reason these tests are worth having.
"""

import pytest
from django_tenants.utils import schema_context

from conftest import PASSWORD, TENANT_A, TENANT_B

pytestmark = pytest.mark.django_db


def _login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")


class TestCrossSchoolLogin:
    def test_a_membership_grants_access_to_that_school(
        self, api_a, identity_ana, grant_membership, tenant_a
    ):
        grant_membership(identity_ana, tenant_a, role="school_admin")

        response = _login(api_a, identity_ana.email)

        assert response.status_code == 200, response.data
        assert response.data["user"]["email"] == identity_ana.email
        assert response.data["user"]["role"] == "school_admin"

    def test_one_password_opens_both_schools_with_different_roles(
        self, api_a, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        """The whole point: one password, two schools, a different role in each."""
        grant_membership(identity_ana, tenant_a, role="school_admin")
        grant_membership(identity_ana, tenant_b, role="teacher")

        at_a = _login(api_a, identity_ana.email)
        assert at_a.status_code == 200
        assert at_a.data["tenant"]["schema"] == TENANT_A["schema"]
        assert at_a.data["user"]["role"] == "school_admin"

        # No second sign-in: the session moves, on the same host.
        at_b = api_a.post(
            "/api/v1/auth/switch/",
            {"tenant_id": str(tenant_b.id)},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {at_a.data['access']}",
        )
        assert at_b.status_code == 200
        assert at_b.data["tenant"]["schema"] == TENANT_B["schema"]
        assert at_b.data["user"]["role"] == "teacher"

    def test_the_login_response_lists_every_school(
        self, api_a, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        """So the client can render a switcher without a second request."""
        grant_membership(identity_ana, tenant_a)
        grant_membership(identity_ana, tenant_b)

        schools = _login(api_a, identity_ana.email).data["schools"]

        by_schema = {row["schema"]: row for row in schools}
        assert set(by_schema) == {TENANT_A["schema"], TENANT_B["schema"]}
        assert by_schema[TENANT_A["schema"]]["is_current"] is True
        # Carries what the interface needs to repaint on switching.
        assert by_schema[TENANT_B["schema"]]["brand_color"]
        assert by_schema[TENANT_B["schema"]]["default_currency"]

    def test_a_single_school_account_lists_just_that_school(self, api_a, admin_a):
        """One entry, so the client knows where it is and renders no switcher."""
        schools = _login(api_a, admin_a.email).data["schools"]

        assert [row["schema"] for row in schools] == [TENANT_A["schema"]]
        assert schools[0]["is_current"] is True

    def test_a_platform_operator_has_no_schools(self, api_public, platform_admin):
        """They are above every institution, not a member of any."""
        response = _login(api_public, platform_admin.email)

        assert response.data["schools"] == []
        assert response.data["tenant"]["schema"] == "public"

    def test_switching_to_a_school_you_do_not_belong_to_is_refused(
        self, api_a, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        grant_membership(identity_ana, tenant_a)
        token = _login(api_a, identity_ana.email).data["access"]

        response = api_a.post(
            "/api/v1/auth/switch/",
            {"tenant_id": str(tenant_b.id)},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        assert response.status_code == 400

    def test_the_school_used_last_is_the_one_reopened(
        self, api_a, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        """Someone who works mostly at one place is not asked every morning."""
        grant_membership(identity_ana, tenant_a)
        grant_membership(identity_ana, tenant_b)

        first = _login(api_a, identity_ana.email)
        api_a.post(
            "/api/v1/auth/switch/",
            {"tenant_id": str(tenant_b.id)},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {first.data['access']}",
        )

        again = _login(api_a, identity_ana.email)
        assert again.data["tenant"]["schema"] == TENANT_B["schema"]

    def test_without_any_membership_there_is_nowhere_to_go(self, api_a, identity_ana):
        """Correct password, no school.

        403 rather than 401 on purpose: the credential is fine, and answering
        "wrong password" would send someone to reset one that works.
        """
        response = _login(api_a, identity_ana.email)

        assert response.status_code == 403
        assert response.data["error"]["code"] == "no_school_access"

    def test_a_wrong_password_never_says_whether_the_account_exists(self, api_a, identity_ana):
        """Otherwise the login form is an account enumerator."""
        unknown = _login(api_a, "nobody@nowhere.test", password="whatever")
        wrong_password = _login(api_a, identity_ana.email, password="not-the-password")

        assert unknown.status_code == wrong_password.status_code == 401
        assert unknown.data == wrong_password.data

    def test_revoking_a_membership_blocks_the_next_login(
        self, api_a, identity_ana, grant_membership, tenant_a
    ):
        membership = grant_membership(identity_ana, tenant_a)
        assert _login(api_a, identity_ana.email).status_code == 200

        with schema_context("public"):
            membership.delete()  # soft

        assert _login(api_a, identity_ana.email).status_code == 403

    def test_deactivating_the_person_blocks_every_school_at_once(
        self, api_a, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        """One credential means one place to revoke it."""
        grant_membership(identity_ana, tenant_a)
        grant_membership(identity_ana, tenant_b)

        with schema_context("public"):
            identity_ana.delete()  # soft

        assert _login(api_a, identity_ana.email).status_code == 401


class TestTheSchoolLocalRow:
    def test_first_login_creates_the_row_inside_the_school(
        self, api_a, identity_ana, grant_membership, tenant_a
    ):
        """Enrollments and invoices point at a school-local user, so one must exist."""
        from apps.users.models import User

        grant_membership(identity_ana, tenant_a, role="school_admin")

        with schema_context(TENANT_A["schema"]):
            assert not User.all_objects.filter(email=identity_ana.email).exists()

        assert _login(api_a, identity_ana.email).status_code == 200

        with schema_context(TENANT_A["schema"]):
            user = User.objects.get(email=identity_ana.email)
            assert user.identity_id == identity_ana.id
            assert user.role == "school_admin"

    def test_the_local_row_has_no_usable_password(
        self, api_a, identity_ana, grant_membership, tenant_a
    ):
        """A second password here could drift from the real one."""
        from apps.users.models import User

        grant_membership(identity_ana, tenant_a)
        _login(api_a, identity_ana.email)

        with schema_context(TENANT_A["schema"]):
            user = User.objects.get(email=identity_ana.email)
            assert not user.has_usable_password()
            assert not user.check_password(PASSWORD)

    def test_a_password_change_takes_effect_everywhere_immediately(
        self, api_a, api_b, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        """No propagation step exists, because there is only one copy."""
        grant_membership(identity_ana, tenant_a)
        grant_membership(identity_ana, tenant_b)
        _login(api_a, identity_ana.email)
        _login(api_b, identity_ana.email)

        with schema_context("public"):
            identity_ana.set_password("Rotated!2026pass")
            identity_ana.save(update_fields=["password", "updated_at"])

        assert _login(api_a, identity_ana.email).status_code == 401
        assert _login(api_a, identity_ana.email, "Rotated!2026pass").status_code == 200
        assert _login(api_b, identity_ana.email, "Rotated!2026pass").status_code == 200

    def test_an_existing_local_account_is_adopted_not_duplicated(
        self, api_a, identity_ana, grant_membership, tenant_a
    ):
        """Hired locally first, given platform access later."""
        from apps.users.models import User

        with schema_context(TENANT_A["schema"]):
            local = User.objects.create_user(
                email=identity_ana.email,
                password="Local!2026pass",
                first_name="Ana",
                last_name="Old",
                role="teacher",
            )

        grant_membership(identity_ana, tenant_a, role="school_admin")
        assert _login(api_a, identity_ana.email).status_code == 200

        with schema_context(TENANT_A["schema"]):
            assert User.all_objects.filter(email=identity_ana.email).count() == 1
            local.refresh_from_db()
            assert local.identity_id == identity_ana.id
            # The membership is the authority on the role.
            assert local.role == "school_admin"


class TestBothPartiesCanSayNo:
    """The platform grants access; the school can still withdraw it."""

    def test_deactivating_the_account_at_one_school_blocks_it_there(
        self, api_a, identity_ana, grant_membership, tenant_a
    ):
        from apps.users.models import User

        grant_membership(identity_ana, tenant_a)
        assert _login(api_a, identity_ana.email).status_code == 200

        with schema_context(TENANT_A["schema"]):
            User.objects.get(email=identity_ana.email).delete()  # soft

        # Their only school refused them, so there is nowhere to open.
        assert _login(api_a, identity_ana.email).status_code == 403

    def test_it_does_not_block_the_person_at_their_other_schools(
        self, api_a, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        """One school's decision is one school's decision."""
        from apps.users.models import User

        grant_membership(identity_ana, tenant_a)
        grant_membership(identity_ana, tenant_b)
        first = _login(api_a, identity_ana.email)
        assert first.data["tenant"]["schema"] == TENANT_A["schema"]

        with schema_context(TENANT_A["schema"]):
            User.objects.get(email=identity_ana.email).delete()

        # Signing in again skips the school that refused and opens the other.
        again = _login(api_a, identity_ana.email)
        assert again.status_code == 200
        assert again.data["tenant"]["schema"] == TENANT_B["schema"]


class TestSingleSchoolAccountsAreUnaffected:
    def test_a_local_account_still_signs_in(self, api_a, admin_a):
        """The identity backend declines, and ModelBackend answers as before."""
        assert _login(api_a, admin_a.email).status_code == 200

    def test_a_platform_operator_still_signs_in(self, api_public, platform_admin):
        assert _login(api_public, platform_admin.email).status_code == 200

    def test_an_operator_reports_no_schools(self, as_platform):
        response = as_platform.get("/api/v1/auth/schools/")

        assert response.status_code == 200
        assert response.data == []


class TestAvailableSchools:
    def test_lists_every_school_the_person_can_reach(
        self, api_a, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        grant_membership(identity_ana, tenant_a, role="school_admin")
        grant_membership(identity_ana, tenant_b, role="teacher")
        token = _login(api_a, identity_ana.email).data["access"]
        api_a.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_a.get("/api/v1/auth/schools/")

        assert response.status_code == 200
        by_schema = {row["schema"]: row for row in response.data}
        assert set(by_schema) == {TENANT_A["schema"], TENANT_B["schema"]}
        assert by_schema[TENANT_A["schema"]]["is_current"] is True
        assert by_schema[TENANT_B["schema"]]["is_current"] is False
        # Enough to repaint the interface without another round trip.
        assert by_schema[TENANT_B["schema"]]["brand_color"]
        assert by_schema[TENANT_B["schema"]]["role"] == "teacher"

    def test_a_revoked_school_disappears_from_the_list(
        self, api_a, identity_ana, grant_membership, tenant_a, tenant_b
    ):
        grant_membership(identity_ana, tenant_a)
        second = grant_membership(identity_ana, tenant_b)
        token = _login(api_a, identity_ana.email).data["access"]
        api_a.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        with schema_context("public"):
            second.delete()

        response = api_a.get("/api/v1/auth/schools/")
        assert [row["schema"] for row in response.data] == [TENANT_A["schema"]]
