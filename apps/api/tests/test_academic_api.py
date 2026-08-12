"""
Academic API, with an emphasis on translated database fields.

`django-modeltranslation` stores one column per language and swaps in the active
one on read. These tests pin that behaviour down at the HTTP boundary, because
it is invisible in the model layer and easy to regress.
"""

import pytest
from django_tenants.utils import schema_context

from conftest import TENANT_A

pytestmark = pytest.mark.django_db


class TestProgramTranslations:
    def test_name_follows_accept_language(self, as_admin_a, program_a):
        spanish = as_admin_a.get(
            f"/api/v1/academic/programs/{program_a.id}/", HTTP_ACCEPT_LANGUAGE="es"
        )
        english = as_admin_a.get(
            f"/api/v1/academic/programs/{program_a.id}/", HTTP_ACCEPT_LANGUAGE="en"
        )

        assert spanish.data["name"] == "Educación Primaria"
        assert english.data["name"] == "Primary Education"

    def test_clients_never_see_the_per_language_columns(self, as_admin_a, program_a):
        response = as_admin_a.get(f"/api/v1/academic/programs/{program_a.id}/")
        assert "name" in response.data
        assert "name_es" not in response.data
        assert "name_en" not in response.data

    def test_translations_view_exposes_every_language(self, as_admin_a, program_a):
        response = as_admin_a.get("/api/v1/academic/programs/", {"translations": "all"})
        assert response.status_code == 200
        row = response.data["results"][0]
        assert row["name_es"] == "Educación Primaria"
        assert row["name_en"] == "Primary Education"

    def test_code_is_not_translated(self, as_admin_a, program_a):
        """Registration codes must be stable across languages."""
        spanish = as_admin_a.get(
            f"/api/v1/academic/programs/{program_a.id}/", HTTP_ACCEPT_LANGUAGE="es"
        )
        english = as_admin_a.get(
            f"/api/v1/academic/programs/{program_a.id}/", HTTP_ACCEPT_LANGUAGE="en"
        )
        assert spanish.data["code"] == english.data["code"] == "PRI"

    def test_create_needs_only_the_default_language(self, as_admin_a):
        """Spanish alone is enough; English and descriptions are optional.

        Regression test: modeltranslation's generated columns are inferred by
        DRF as required/non-blank, which made it impossible to save a programme
        without filling in every language.
        """
        response = as_admin_a.post(
            "/api/v1/academic/programs/?translations=all",
            {"code": "MINIMAL", "name_es": "Solo español"},
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["name_es"] == "Solo español"

    def test_create_still_requires_spanish(self, as_admin_a):
        response = as_admin_a.post(
            "/api/v1/academic/programs/?translations=all",
            {"code": "NOSPANISH", "name_en": "English only"},
            format="json",
        )
        assert response.status_code == 400
        assert "name_es" in response.data["error"]["details"]

    def test_missing_english_falls_back_to_spanish(self, as_admin_a, tenant_a):
        from apps.academic.models import Program

        with schema_context(TENANT_A["schema"]):
            program = Program.objects.create(code="ONLYES", name_es="Solo español")

        response = as_admin_a.get(
            f"/api/v1/academic/programs/{program.id}/", HTTP_ACCEPT_LANGUAGE="en"
        )
        assert response.data["name"] == "Solo español"


class TestAcademicYear:
    def test_create_requires_staff(self, as_student_a):
        response = as_student_a.post(
            "/api/v1/academic/academic-years/",
            {"name": "2030-2031", "start_date": "2030-09-01", "end_date": "2031-06-30"},
            format="json",
        )
        assert response.status_code == 403

    def test_admin_can_create(self, as_admin_a):
        response = as_admin_a.post(
            "/api/v1/academic/academic-years/",
            {"name": "2030-2031", "start_date": "2030-09-01", "end_date": "2031-06-30"},
            format="json",
        )
        assert response.status_code == 201, response.data

    def test_end_date_must_follow_start_date(self, as_admin_a):
        response = as_admin_a.post(
            "/api/v1/academic/academic-years/",
            {"name": "Broken", "start_date": "2030-09-01", "end_date": "2030-08-01"},
            format="json",
        )
        assert response.status_code == 400
        assert "end_date" in response.data["error"]["details"]

    def test_validation_message_is_localised(self, as_admin_a):
        payload = {"name": "Broken", "start_date": "2030-09-01", "end_date": "2030-08-01"}

        spanish = as_admin_a.post(
            "/api/v1/academic/academic-years/", payload, format="json", HTTP_ACCEPT_LANGUAGE="es"
        )
        english = as_admin_a.post(
            "/api/v1/academic/academic-years/", payload, format="json", HTTP_ACCEPT_LANGUAGE="en"
        )

        assert spanish.data["error"]["details"]["end_date"][0].startswith("La fecha")
        assert english.data["error"]["details"]["end_date"][0].startswith("The end date")


class TestSubjects:
    def test_create_and_list(self, as_admin_a, program_a, teacher_a):
        created = as_admin_a.post(
            "/api/v1/academic/subjects/",
            {
                "code": "MAT",
                "name": "Matemáticas",
                "credits": 6,
                "program": str(program_a.id),
                "teacher": str(teacher_a.id),
            },
            format="json",
        )
        assert created.status_code == 201, created.data

        listed = as_admin_a.get("/api/v1/academic/subjects/")
        assert listed.data["count"] == 1
        row = listed.data["results"][0]
        assert row["program_code"] == "PRI"
        assert row["teacher_name"] == teacher_a.get_full_name()

    def test_filter_by_program(self, as_admin_a, program_a, teacher_a):
        as_admin_a.post(
            "/api/v1/academic/subjects/",
            {"code": "MAT", "name": "Matemáticas", "credits": 6, "program": str(program_a.id)},
            format="json",
        )
        response = as_admin_a.get("/api/v1/academic/subjects/", {"program": str(program_a.id)})
        assert response.data["count"] == 1


class TestEnrollments:
    def test_enrollment_is_listed_with_resolved_labels(self, as_admin_a, enrollment_a):
        response = as_admin_a.get("/api/v1/academic/enrollments/")
        assert response.status_code == 200

        row = response.data["results"][0]
        assert row["student_name"] == enrollment_a.student.get_full_name()
        assert row["program_name"] == "Educación Primaria"
        assert row["status"] == "active"

    def test_filter_by_status(self, as_admin_a, enrollment_a):
        assert (
            as_admin_a.get("/api/v1/academic/enrollments/", {"status": "active"}).data["count"] == 1
        )
        assert (
            as_admin_a.get("/api/v1/academic/enrollments/", {"status": "withdrawn"}).data["count"]
            == 0
        )

    def test_deleting_an_enrollment_is_soft(self, as_admin_a, enrollment_a):
        from apps.academic.models import Enrollment

        assert (
            as_admin_a.delete(f"/api/v1/academic/enrollments/{enrollment_a.id}/").status_code == 204
        )

        with schema_context(TENANT_A["schema"]):
            assert not Enrollment.objects.filter(pk=enrollment_a.id).exists()
            assert Enrollment.all_objects.filter(pk=enrollment_a.id).exists()
