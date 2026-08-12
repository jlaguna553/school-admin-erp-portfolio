"""
Who reaches what, and what an institution has switched on.

Two mechanisms that look alike and are not. **Rank** is an administrative
ladder: it decides who may act on whom. **Reach** is per module and is declared,
not derived -- an accountant sits below a coordinator on the ladder and is
nonetheless the only one of the two who belongs in billing. A single ordering
would have to choose between letting coordinators into invoices and locking
accountants out, and both are wrong.
"""

import pytest

from apps.core import modules
from apps.core.roles import assignable_roles, outranks, rank_of
from conftest import TENANT_A, tenant_setting

pytestmark = pytest.mark.django_db


class TestTheLadder:
    def test_it_is_ordered_from_the_platform_down(self) -> None:
        assert rank_of("platform_admin") > rank_of("school_admin")
        assert rank_of("school_admin") > rank_of("coordinator")
        assert rank_of("teacher") > rank_of("student")

    def test_an_unknown_role_ranks_below_everything(self) -> None:
        """A typo in the database should cost access, never grant it."""
        assert rank_of("wat") == 0
        assert not outranks("wat", "student")
        assert outranks("student", "wat")

    def test_peers_cannot_act_on_each_other(self) -> None:
        """Otherwise two administrators could deactivate one another."""
        assert not outranks("school_admin", "school_admin")

    def test_nobody_appoints_their_own_rank(self) -> None:
        assert "school_admin" not in assignable_roles("school_admin")
        assert "coordinator" in assignable_roles("school_admin")

    def test_the_top_role_is_the_one_exception(self) -> None:
        """Or the platform could never gain a second operator through the product."""
        assert "platform_admin" in assignable_roles("platform_admin")


class TestReachIsNotRank:
    def test_the_accountant_outreaches_the_coordinator_in_billing(self) -> None:
        assert rank_of("accountant") < rank_of("coordinator")
        assert modules.may_write(modules.Module.BILLING, "accountant")
        assert not modules.may_read(modules.Module.BILLING, "coordinator")

    def test_a_teacher_reads_academic_but_does_not_write_it(self) -> None:
        assert modules.may_read(modules.Module.ACADEMIC, "teacher")
        assert not modules.may_write(modules.Module.ACADEMIC, "teacher")

    def test_a_student_reaches_no_module(self) -> None:
        for key in modules.MODULES:
            assert not modules.may_read(key, "student"), key


class TestRolesEndpointFollowsTheLadder:
    def test_an_administrator_is_offered_only_what_they_may_grant(self, as_admin_a):
        values = {row["value"] for row in as_admin_a.get("/api/v1/users/roles/").data}

        assert "coordinator" in values
        # Offering these would advertise a privilege the API then refuses.
        assert "school_admin" not in values
        assert "platform_admin" not in values

    def test_a_coordinator_is_offered_less_than_an_administrator(self, as_coordinator_a):
        values = {row["value"] for row in as_coordinator_a.get("/api/v1/users/roles/").data}

        assert "teacher" in values
        assert "coordinator" not in values
        assert "school_admin" not in values


class TestActingOnPeople:
    def test_a_coordinator_cannot_edit_the_administrator_above_them(
        self, as_coordinator_a, admin_a
    ):
        response = as_coordinator_a.patch(
            f"/api/v1/users/{admin_a.id}/", {"first_name": "Reassigned"}, format="json"
        )

        assert response.status_code == 403

    def test_an_administrator_can_edit_someone_below_them(self, as_admin_a, teacher_a):
        response = as_admin_a.patch(
            f"/api/v1/users/{teacher_a.id}/", {"first_name": "Renamed"}, format="json"
        )

        assert response.status_code == 200

    def test_editing_yourself_is_a_different_endpoint(self, as_coordinator_a, coordinator_a):
        """Self-service is `me/`, which every role reaches.

        Routing it through the administration endpoint instead would mean a
        student needed read access to the whole staff directory in order to
        change their own phone number.
        """
        via_admin = as_coordinator_a.patch(
            f"/api/v1/users/{coordinator_a.id}/", {"first_name": "Yo"}, format="json"
        )
        via_me = as_coordinator_a.patch("/api/v1/users/me/", {"first_name": "Yo"}, format="json")

        assert via_admin.status_code == 403
        assert via_me.status_code == 200


class TestSwitchingModulesOff:
    def test_a_disabled_module_is_refused_to_everyone(self, as_admin_a):
        """Including the administrator: "off for most people" is not a setting."""
        assert as_admin_a.get("/api/v1/billing/invoices/").status_code == 200

        with tenant_setting(TENANT_A["schema"], disabled_modules=["billing"]):
            response = as_admin_a.get("/api/v1/billing/invoices/")

        assert response.status_code == 403
        assert response.data["error"]["code"] == "module_disabled"

    def test_it_only_affects_the_module_switched_off(self, as_admin_a):
        with tenant_setting(TENANT_A["schema"], disabled_modules=["billing"]):
            assert as_admin_a.get("/api/v1/academic/programs/").status_code == 200
            assert as_admin_a.get("/api/v1/users/").status_code == 200

    def test_it_only_affects_the_institution_that_switched_it_off(self, as_admin_a, api_b, admin_b):
        from conftest import PASSWORD

        with tenant_setting(TENANT_A["schema"], disabled_modules=["billing"]):
            token = api_b.post(
                "/api/v1/auth/login/",
                {"email": admin_b.email, "password": PASSWORD},
                format="json",
            ).data["access"]
            api_b.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

            assert as_admin_a.get("/api/v1/billing/invoices/").status_code == 403
            assert api_b.get("/api/v1/billing/invoices/").status_code == 200

    def test_the_session_reports_what_is_on(self, api_a, admin_a):
        from conftest import PASSWORD

        with tenant_setting(TENANT_A["schema"], disabled_modules=["billing", "schedule"]):
            response = api_a.post(
                "/api/v1/auth/login/",
                {"email": admin_a.email, "password": PASSWORD},
                format="json",
            )

        enabled = response.data["tenant"]["modules"]
        assert "billing" not in enabled
        assert "schedule" not in enabled
        assert "users" in enabled

    def test_a_module_the_product_needs_cannot_be_switched_off(self, as_platform, tenant_a):
        response = as_platform.patch(
            f"/api/v1/tenants/{tenant_a.id}/", {"disabled_modules": ["users"]}, format="json"
        )

        assert response.status_code == 400
        assert "disabled_modules" in response.data["error"]["details"]

    def test_a_module_shipped_later_is_on_by_default(self) -> None:
        """Institutions store what they switched off, not what they have on.

        An "enabled" list would leave every school provisioned before a release
        silently missing whatever that release added.
        """
        assert set(modules.enabled_modules([])) == set(modules.MODULES)
        assert set(modules.enabled_modules(None)) == set(modules.MODULES)
