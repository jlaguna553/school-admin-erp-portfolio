"""Users API: permissions, soft delete and self-service."""

import pytest
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

from conftest import PASSWORD, TENANT_A

pytestmark = pytest.mark.django_db


class TestListingAndFiltering:
    def test_admin_can_list_users(self, as_admin_a, student_a, teacher_a):
        response = as_admin_a.get("/api/v1/users/")
        assert response.status_code == 200
        assert response.data["count"] >= 3
        # Pagination contract the frontend table depends on.
        for key in ("count", "total_pages", "page", "page_size", "results"):
            assert key in response.data

    def test_filter_by_role(self, as_admin_a, student_a, teacher_a):
        response = as_admin_a.get("/api/v1/users/", {"role": "student"})
        assert response.status_code == 200
        assert {row["role"] for row in response.data["results"]} == {"student"}

    def test_search_by_name(self, as_admin_a, tenant_a):
        get_user_model()
        with schema_context(TENANT_A["schema"]):
            get_user_model().objects.create_user(
                email="zoe.searchable@alpha.test",
                password=PASSWORD,
                first_name="Zoe",
                last_name="Searchable",
                role="student",
            )
        response = as_admin_a.get("/api/v1/users/", {"search": "Searchable"})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["email"] == "zoe.searchable@alpha.test"

    def test_page_size_is_honoured(self, as_admin_a, student_a, teacher_a):
        response = as_admin_a.get("/api/v1/users/", {"page_size": 1})
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["page_size"] == 1


class TestPermissions:
    def test_a_student_reaches_nothing_administrative(self, as_student_a):
        """Reading the staff directory used to be allowed, and should not be.

        Every authenticated user could list the institution's people, which
        hands a student their teachers' addresses and phone numbers. Roles only
        constrained writes; now they constrain reach.
        """
        assert as_student_a.get("/api/v1/users/").status_code == 403
        assert as_student_a.get("/api/v1/academic/programs/").status_code == 403
        assert as_student_a.get("/api/v1/billing/invoices/").status_code == 403

        response = as_student_a.post(
            "/api/v1/users/",
            {
                "email": "sneaky@alpha.test",
                "first_name": "S",
                "last_name": "N",
                "role": "school_admin",
                "password": PASSWORD,
            },
            format="json",
        )
        assert response.status_code == 403

    def test_a_student_still_reaches_their_own_profile(self, as_student_a):
        """The hierarchy narrows what they administer, not who they are."""
        assert as_student_a.get("/api/v1/users/me/").status_code == 200

    def test_admin_can_create(self, as_admin_a):
        response = as_admin_a.post(
            "/api/v1/users/",
            {
                "email": "New.Teacher@Alpha.test",
                "first_name": "New",
                "last_name": "Teacher",
                "role": "teacher",
                "password": PASSWORD,
            },
            format="json",
        )
        assert response.status_code == 201, response.data

        with schema_context(TENANT_A["schema"]):
            # The serializer normalises the address to lowercase.
            assert get_user_model().objects.filter(email="new.teacher@alpha.test").exists()

    def test_duplicate_email_is_rejected_with_field_error(self, as_admin_a, student_a):
        response = as_admin_a.post(
            "/api/v1/users/",
            {
                "email": student_a.email,
                "first_name": "Dup",
                "last_name": "Licate",
                "role": "student",
                "password": PASSWORD,
            },
            format="json",
        )
        assert response.status_code == 400
        # The envelope carries per-field detail so forms can map it to inputs.
        assert "email" in response.data["error"]["details"]

    def test_weak_password_is_rejected(self, as_admin_a):
        response = as_admin_a.post(
            "/api/v1/users/",
            {
                "email": "weak@alpha.test",
                "first_name": "Weak",
                "last_name": "Password",
                "role": "student",
                "password": "123",
            },
            format="json",
        )
        assert response.status_code == 400
        assert "password" in response.data["error"]["details"]


class TestSoftDelete:
    def test_delete_deactivates_and_keeps_the_row(self, as_admin_a, student_a):
        response = as_admin_a.delete(f"/api/v1/users/{student_a.id}/")
        assert response.status_code == 204

        with schema_context(TENANT_A["schema"]):
            user_model = get_user_model()
            # Gone from the default manager...
            assert not user_model.objects.filter(pk=student_a.id).exists()
            # ...but the record is retained.
            deleted = user_model.all_objects.get(pk=student_a.id)
            assert deleted.is_active is False
            assert deleted.deleted_at is not None

    def test_deactivated_user_disappears_from_the_list(self, as_admin_a, student_a):
        as_admin_a.delete(f"/api/v1/users/{student_a.id}/")
        response = as_admin_a.get("/api/v1/users/")
        assert student_a.email not in {row["email"] for row in response.data["results"]}

    def test_deactivated_user_cannot_log_in(self, api_a, as_admin_a, student_a):
        as_admin_a.delete(f"/api/v1/users/{student_a.id}/")

        response = api_a.post(
            "/api/v1/auth/login/",
            {"email": student_a.email, "password": PASSWORD},
            format="json",
        )
        # 403, not 401: the credential is fine and lives platform-wide, so
        # "wrong password" would send someone to reset a password that works.
        # What they have lost is access to the only school they belonged to.
        assert response.status_code == 403

    def test_restore_brings_the_user_back(self, as_admin_a, student_a):
        as_admin_a.delete(f"/api/v1/users/{student_a.id}/")

        with schema_context(TENANT_A["schema"]):
            user_model = get_user_model()
            user_model.all_objects.get(pk=student_a.id).restore()
            assert user_model.objects.filter(pk=student_a.id).exists()

    def test_queryset_delete_is_also_soft(self, tenant_a, student_a):
        """Bulk delete must not bypass the rule."""
        with schema_context(TENANT_A["schema"]):
            user_model = get_user_model()
            user_model.objects.filter(pk=student_a.id).delete()

            assert not user_model.objects.filter(pk=student_a.id).exists()
            assert user_model.all_objects.filter(pk=student_a.id).exists()


class TestSelfService:
    def test_me_returns_the_authenticated_user(self, as_admin_a, admin_a):
        response = as_admin_a.get("/api/v1/users/me/")
        assert response.status_code == 200
        assert response.data["email"] == admin_a.email
        assert response.data["role"] == "school_admin"

    def test_me_is_available_to_every_role(self, as_student_a, student_a):
        response = as_student_a.get("/api/v1/users/me/")
        assert response.status_code == 200
        assert response.data["email"] == student_a.email

    def test_patch_me_updates_language(self, as_student_a, student_a):
        response = as_student_a.patch("/api/v1/users/me/", {"language": "en"}, format="json")
        assert response.status_code == 200
        assert response.data["language"] == "en"

        # The connection is put back on `public` when a request ends, so a
        # school-local row has to be re-read inside its own schema.
        with schema_context(TENANT_A["schema"]):
            student_a.refresh_from_db()
        assert student_a.language == "en"

    def test_patch_me_cannot_escalate_role(self, as_student_a, student_a):
        """`role` is read-only on the self-service serializer."""
        response = as_student_a.patch("/api/v1/users/me/", {"role": "school_admin"}, format="json")
        assert response.status_code == 200

        with schema_context(TENANT_A["schema"]):
            student_a.refresh_from_db()
        assert student_a.role == "student"

    def test_change_password(self, api_a, as_student_a, student_a):
        new_password = "Rotated!2026pass"
        response = as_student_a.post(
            "/api/v1/users/me/change-password/",
            {"current_password": PASSWORD, "new_password": new_password},
            format="json",
        )
        assert response.status_code == 204

        assert (
            api_a.post(
                "/api/v1/auth/login/",
                {"email": student_a.email, "password": new_password},
                format="json",
            ).status_code
            == 200
        )
        assert (
            api_a.post(
                "/api/v1/auth/login/",
                {"email": student_a.email, "password": PASSWORD},
                format="json",
            ).status_code
            == 401
        )

    def test_change_password_rejects_wrong_current(self, as_student_a):
        response = as_student_a.post(
            "/api/v1/users/me/change-password/",
            {"current_password": "not-the-password", "new_password": "Another!2026pw"},
            format="json",
        )
        assert response.status_code == 400
        assert "current_password" in response.data["error"]["details"]

    def test_roles_endpoint_is_localised(self, as_admin_a):
        spanish = as_admin_a.get("/api/v1/users/roles/", HTTP_ACCEPT_LANGUAGE="es")
        english = as_admin_a.get("/api/v1/users/roles/", HTTP_ACCEPT_LANGUAGE="en")

        assert spanish.status_code == 200
        labels_es = {row["value"]: row["label"] for row in spanish.data}
        labels_en = {row["value"]: row["label"] for row in english.data}

        assert labels_es["teacher"] == "Docente"
        assert labels_en["teacher"] == "Teacher"
