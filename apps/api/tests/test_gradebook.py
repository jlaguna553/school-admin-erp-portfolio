"""
Marks, and the average they add up to.

The average is the number families argue about, so the rules it follows are
pinned here rather than left to whoever reads the code next: scores are
normalised before they are weighted, ungraded work is excluded rather than
counted as zero, and the scale the result is reported on is predictable.
"""

from decimal import Decimal

import pytest
from django_tenants.utils import schema_context

from conftest import TENANT_A, tenant_setting

pytestmark = pytest.mark.django_db

TERMS = "/api/v1/academic/terms/"
ASSESSMENTS = "/api/v1/academic/assessments/"
GRADEBOOK = "/api/v1/academic/gradebook/"


def _assessment(client, subject, term, *, name, max_score="10.00", weight="1.00"):
    response = client.post(
        ASSESSMENTS,
        {
            "subject": str(subject.id),
            "term": str(term.id),
            "name": name,
            "max_score": max_score,
            "weight": weight,
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    return response.data["id"]


def _record(client, assessment_id, entries):
    return client.put(f"{ASSESSMENTS}{assessment_id}/grades/", entries, format="json")


class TestTheAverage:
    def test_scores_are_normalised_before_they_are_weighted(
        self, as_admin_a, subject_a, term_a, enrollment_a
    ):
        """An exam out of 100 must not dominate homework out of 10 by scale alone."""
        exam = _assessment(
            as_admin_a, subject_a, term_a, name="Examen", max_score="100.00", weight="3.00"
        )
        homework = _assessment(as_admin_a, subject_a, term_a, name="Tareas", max_score="10.00")

        _record(as_admin_a, exam, [{"enrollment_id": str(enrollment_a.id), "score": "85.00"}])
        _record(as_admin_a, homework, [{"enrollment_id": str(enrollment_a.id), "score": "9.00"}])

        row = self._row(as_admin_a, subject_a, term_a, enrollment_a)
        # (0.85 * 3 + 0.90 * 1) / 4 = 0.8625, on the fallback percentage scale.
        assert Decimal(row["average"]) == Decimal("86.25")

    def test_ungraded_work_is_excluded_not_counted_as_zero(
        self, as_admin_a, subject_a, term_a, enrollment_a
    ):
        """Otherwise every student fails until the last exam is marked."""
        first = _assessment(as_admin_a, subject_a, term_a, name="Primero")
        _assessment(as_admin_a, subject_a, term_a, name="Segundo")

        _record(as_admin_a, first, [{"enrollment_id": str(enrollment_a.id), "score": "8.00"}])

        row = self._row(as_admin_a, subject_a, term_a, enrollment_a)
        assert Decimal(row["average"]) == Decimal("8.00")
        assert row["graded_count"] == 1

    def test_no_marks_reads_as_nothing_not_as_zero(
        self, as_admin_a, subject_a, term_a, enrollment_a
    ):
        """ "Not marked" and "marked zero" are different claims about a student."""
        _assessment(as_admin_a, subject_a, term_a, name="Examen")

        row = self._row(as_admin_a, subject_a, term_a, enrollment_a)
        assert row["average"] is None
        assert row["graded_count"] == 0

    def test_a_mark_of_zero_is_kept(self, as_admin_a, subject_a, term_a, enrollment_a):
        exam = _assessment(as_admin_a, subject_a, term_a, name="Examen")
        _record(as_admin_a, exam, [{"enrollment_id": str(enrollment_a.id), "score": "0.00"}])

        row = self._row(as_admin_a, subject_a, term_a, enrollment_a)
        assert Decimal(row["average"]) == Decimal("0.00")
        assert row["graded_count"] == 1

    def test_one_shared_scale_is_reported_on_that_scale(
        self, as_admin_a, subject_a, term_a, enrollment_a
    ):
        """A school marking everything out of 10 should read averages out of 10."""
        first = _assessment(as_admin_a, subject_a, term_a, name="Primero", max_score="10.00")
        _assessment(as_admin_a, subject_a, term_a, name="Segundo", max_score="10.00")
        _record(as_admin_a, first, [{"enrollment_id": str(enrollment_a.id), "score": "9.00"}])

        body = as_admin_a.get(
            GRADEBOOK, {"subject": str(subject_a.id), "term": str(term_a.id)}
        ).data
        assert Decimal(body["average_scale"]) == Decimal("10.00")
        assert Decimal(body["rows"][0]["average"]) == Decimal("9.00")

    def test_mixed_scales_fall_back_to_a_percentage(
        self, as_admin_a, subject_a, term_a, enrollment_a
    ):
        """Rather than borrowing whichever assessment happens to sort first."""
        _assessment(as_admin_a, subject_a, term_a, name="Examen", max_score="100.00")
        _assessment(as_admin_a, subject_a, term_a, name="Tareas", max_score="10.00")

        body = as_admin_a.get(
            GRADEBOOK, {"subject": str(subject_a.id), "term": str(term_a.id)}
        ).data
        assert Decimal(body["average_scale"]) == Decimal("100.00")

    @staticmethod
    def _row(client, subject, term, enrollment):
        body = client.get(GRADEBOOK, {"subject": str(subject.id), "term": str(term.id)}).data
        return next(row for row in body["rows"] if row["enrollment_id"] == str(enrollment.id))


class TestRecordingMarks:
    def test_a_column_is_written_in_one_call(self, as_admin_a, subject_a, term_a, enrollment_a):
        exam = _assessment(as_admin_a, subject_a, term_a, name="Examen")

        response = _record(
            as_admin_a, exam, [{"enrollment_id": str(enrollment_a.id), "score": "7.50"}]
        )

        assert response.status_code == 200
        assert Decimal(response.data[0]["score"]) == Decimal("7.50")

    def test_writing_again_replaces_rather_than_duplicates(
        self, as_admin_a, subject_a, term_a, enrollment_a
    ):
        from apps.academic.models import Grade

        exam = _assessment(as_admin_a, subject_a, term_a, name="Examen")
        _record(as_admin_a, exam, [{"enrollment_id": str(enrollment_a.id), "score": "5.00"}])
        _record(as_admin_a, exam, [{"enrollment_id": str(enrollment_a.id), "score": "8.00"}])

        with schema_context(TENANT_A["schema"]):
            grades = Grade.objects.filter(assessment_id=exam)
            assert grades.count() == 1
            assert grades.first().score == Decimal("8.00")

    def test_a_null_score_clears_the_mark(self, as_admin_a, subject_a, term_a, enrollment_a):
        """Distinct from writing a zero, which is a mark."""
        exam = _assessment(as_admin_a, subject_a, term_a, name="Examen")
        _record(as_admin_a, exam, [{"enrollment_id": str(enrollment_a.id), "score": "5.00"}])
        _record(as_admin_a, exam, [{"enrollment_id": str(enrollment_a.id), "score": None}])

        row = TestTheAverage._row(as_admin_a, subject_a, term_a, enrollment_a)
        assert row["average"] is None

    def test_a_student_of_another_class_is_ignored(
        self, as_admin_a, subject_a, term_a, enrollment_a
    ):
        """One stale row in a cached grid must not fail the whole column."""
        exam = _assessment(as_admin_a, subject_a, term_a, name="Examen")

        response = _record(
            as_admin_a,
            exam,
            [
                {"enrollment_id": "00000000-0000-0000-0000-000000000000", "score": "9.00"},
                {"enrollment_id": str(enrollment_a.id), "score": "6.00"},
            ],
        )

        assert response.status_code == 200
        assert len(response.data) == 1

    def test_a_score_above_the_maximum_is_capped(self, as_admin_a, subject_a, term_a, enrollment_a):
        exam = _assessment(as_admin_a, subject_a, term_a, name="Examen", max_score="10.00")

        response = _record(
            as_admin_a, exam, [{"enrollment_id": str(enrollment_a.id), "score": "99.00"}]
        )

        assert Decimal(response.data[0]["score"]) == Decimal("10.00")


class TestWhoMayMark:
    def test_a_teacher_marks_their_own_subject(
        self, as_teacher_a, subject_a, term_a, enrollment_a, as_admin_a
    ):
        """`subject_a` is assigned to `teacher_a`."""
        exam = _assessment(as_admin_a, subject_a, term_a, name="Examen")

        response = _record(
            as_teacher_a, exam, [{"enrollment_id": str(enrollment_a.id), "score": "7.00"}]
        )

        assert response.status_code == 200

    def test_a_teacher_cannot_mark_someone_else_s_subject(
        self, as_admin_a, as_teacher_a, program_a, term_a, enrollment_a, tenant_a
    ):
        """A mark is a claim about a student's work, attributed to whoever made it."""
        from apps.academic.models import Subject

        with schema_context(TENANT_A["schema"]):
            other = Subject.objects.create(
                code="HIS", name="Historia", program=program_a, credits=4, teacher=None
            )

        exam = _assessment(as_admin_a, other, term_a, name="Examen")
        response = _record(
            as_teacher_a, exam, [{"enrollment_id": str(enrollment_a.id), "score": "7.00"}]
        )

        assert response.status_code == 403

    def test_the_gradebook_says_whether_it_is_editable(
        self, as_teacher_a, as_admin_a, subject_a, term_a
    ):
        """So the interface renders inputs or text, instead of offering refused edits."""
        assert (
            as_admin_a.get(GRADEBOOK, {"subject": str(subject_a.id), "term": str(term_a.id)}).data[
                "can_edit"
            ]
            is True
        )

    def test_a_student_reaches_no_part_of_it(self, as_student_a, subject_a, term_a):
        assert as_student_a.get(TERMS).status_code == 403
        assert (
            as_student_a.get(
                GRADEBOOK, {"subject": str(subject_a.id), "term": str(term_a.id)}
            ).status_code
            == 403
        )

    def test_an_accountant_reaches_no_part_of_it(self, as_accountant_a, subject_a, term_a):
        """Reach is per module: finance is not teaching."""
        assert as_accountant_a.get(TERMS).status_code == 403


class TestTheModuleCanBeSwitchedOff:
    def test_a_school_without_the_gradebook_refuses_all_of_it(self, as_admin_a, subject_a, term_a):
        with tenant_setting(TENANT_A["schema"], disabled_modules=["grades"]):
            response = as_admin_a.get(TERMS)

        assert response.status_code == 403
        assert response.data["error"]["code"] == "module_disabled"
