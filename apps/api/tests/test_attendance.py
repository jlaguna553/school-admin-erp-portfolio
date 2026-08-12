"""
Taking the roll.

The distinctions pinned here are the ones a parent phones about: an unmarked
student is not a present one, a cancelled class is not a room full of
absentees, and a day nobody took a roll is not a day of zero attendance.
"""

from datetime import date, time, timedelta

import pytest
from django.utils import timezone
from django_tenants.utils import schema_context

from conftest import TENANT_A, tenant_setting

pytestmark = pytest.mark.django_db

ROLL = "/api/v1/academic/roll/"
TODAY_CLASSES = "/api/v1/academic/classes/today/"
WEEKLY = "/api/v1/academic/attendance/weekly/"

# `slot_a` meets on Mondays; this is one.
A_MONDAY = date(2026, 9, 7)


def _take(client, slot, on, entries, **extra):
    return client.put(
        ROLL,
        {"slot": str(slot.id), "date": on.isoformat(), "entries": entries, **extra},
        format="json",
    )


@pytest.fixture
def slot_today(tenant_a, group_a, subject_a):
    """A class that meets on whatever weekday today is, for trend tests."""
    from apps.academic.models import TimetableSlot

    with schema_context(TENANT_A["schema"]):
        return TimetableSlot.objects.create(
            group=group_a,
            subject=subject_a,
            weekday=timezone.localdate().isoweekday(),
            start_time=time(11, 0),
            end_time=time(12, 0),
        )


class TestTheRegister:
    def test_it_lists_the_group_with_nobody_marked(
        self, as_admin_a, slot_a, enrollment_a, student_a
    ):
        """An untaken roll reports no status -- not a room full of present students."""
        body = as_admin_a.get(ROLL, {"slot": str(slot_a.id), "date": A_MONDAY.isoformat()}).data

        assert body["session"] is None
        assert len(body["rows"]) == 1
        assert body["rows"][0]["student_name"] == student_a.get_full_name()
        assert body["rows"][0]["status"] is None

    def test_it_holds_the_group_not_the_whole_programme(
        self, as_admin_a, slot_a, enrollment_a, program_a, academic_year_a, tenant_a
    ):
        """A teacher looking at one section must not be handed the whole year."""
        from apps.academic.models import Enrollment, EnrollmentStatus, StudentGroup
        from apps.users.models import User, UserRole

        with schema_context(TENANT_A["schema"]):
            elsewhere = StudentGroup.objects.create(
                name="B", program=program_a, academic_year=academic_year_a
            )
            other_student = User.objects.create_user(
                email="otro@alpha.test", password="x", role=UserRole.STUDENT, last_name="Zeta"
            )
            Enrollment.objects.create(
                student=other_student,
                program=program_a,
                academic_year=academic_year_a,
                group=elsewhere,
                status=EnrollmentStatus.ACTIVE,
                enrolled_on=academic_year_a.start_date,
            )

        body = as_admin_a.get(ROLL, {"slot": str(slot_a.id), "date": A_MONDAY.isoformat()}).data

        assert [row["student_name"] for row in body["rows"]] == [
            enrollment_a.student.get_full_name()
        ]

    def test_a_monday_class_has_no_register_on_a_tuesday(self, as_admin_a, slot_a, enrollment_a):
        """A mistyped date would otherwise record absences for a lesson never given."""
        response = as_admin_a.get(
            ROLL, {"slot": str(slot_a.id), "date": (A_MONDAY + timedelta(days=1)).isoformat()}
        )

        assert response.status_code == 400
        assert "date" in response.data["error"]["details"]


class TestTakingIt:
    def test_the_whole_room_is_marked_in_one_call(self, as_admin_a, slot_a, enrollment_a):
        response = _take(
            as_admin_a,
            slot_a,
            A_MONDAY,
            [{"enrollment_id": str(enrollment_a.id), "status": "late"}],
        )

        assert response.status_code == 200
        assert response.data["rows"][0]["status"] == "late"

    def test_it_records_who_took_it(self, as_teacher_a, slot_a, enrollment_a, teacher_a):
        """A register is a claim about where a child was; it carries its author."""
        body = _take(
            as_teacher_a,
            slot_a,
            A_MONDAY,
            [{"enrollment_id": str(enrollment_a.id), "status": "present"}],
        ).data

        assert body["session"]["taken_by_name"] == teacher_a.get_full_name()
        assert body["session"]["taken_at"] is not None

    def test_taking_it_again_replaces_rather_than_duplicates(
        self, as_admin_a, slot_a, enrollment_a
    ):
        from apps.academic.models import Attendance

        _take(
            as_admin_a,
            slot_a,
            A_MONDAY,
            [{"enrollment_id": str(enrollment_a.id), "status": "absent"}],
        )
        body = _take(
            as_admin_a,
            slot_a,
            A_MONDAY,
            [{"enrollment_id": str(enrollment_a.id), "status": "present"}],
        ).data

        assert body["rows"][0]["status"] == "present"
        with schema_context(TENANT_A["schema"]):
            assert Attendance.objects.count() == 1

    def test_a_null_status_erases_the_mark(self, as_admin_a, slot_a, enrollment_a):
        """Back to unrecorded -- which is neither present nor absent."""
        _take(
            as_admin_a,
            slot_a,
            A_MONDAY,
            [{"enrollment_id": str(enrollment_a.id), "status": "absent"}],
        )
        body = _take(
            as_admin_a, slot_a, A_MONDAY, [{"enrollment_id": str(enrollment_a.id), "status": None}]
        ).data

        assert body["rows"][0]["status"] is None

    def test_cancelling_clears_the_absences(self, as_admin_a, slot_a, enrollment_a):
        """A lesson nobody gave cannot count against the students who missed it."""
        _take(
            as_admin_a,
            slot_a,
            A_MONDAY,
            [{"enrollment_id": str(enrollment_a.id), "status": "absent"}],
        )

        body = _take(as_admin_a, slot_a, A_MONDAY, [], status="cancelled", note="Puente").data

        assert body["session"]["status"] == "cancelled"
        assert body["rows"][0]["status"] is None

    def test_a_student_of_another_group_is_ignored(self, as_admin_a, slot_a, enrollment_a):
        """One stale row in an open sheet must not fail the whole register."""
        response = _take(
            as_admin_a,
            slot_a,
            A_MONDAY,
            [
                {"enrollment_id": "00000000-0000-0000-0000-000000000000", "status": "absent"},
                {"enrollment_id": str(enrollment_a.id), "status": "present"},
            ],
        )

        assert response.status_code == 200
        assert len(response.data["rows"]) == 1


class TestWhoMayTakeIt:
    def test_the_teacher_of_the_subject_may(self, as_teacher_a, slot_a, enrollment_a):
        """`subject_a` is assigned to `teacher_a`."""
        assert (
            _take(
                as_teacher_a,
                slot_a,
                A_MONDAY,
                [{"enrollment_id": str(enrollment_a.id), "status": "present"}],
            ).status_code
            == 200
        )

    def test_another_teacher_may_not(self, as_admin_a, slot_a, enrollment_a, tenant_a):
        from conftest import _authenticated_as, _make_user

        _make_user(TENANT_A["schema"], "otro.profe@alpha.test", "teacher")
        other = _authenticated_as("otro.profe@alpha.test")

        response = _take(
            other, slot_a, A_MONDAY, [{"enrollment_id": str(enrollment_a.id), "status": "absent"}]
        )

        assert response.status_code == 403

    def test_the_group_tutor_alone_may_not(
        self, as_admin_a, group_a, enrollment_a, program_a, tenant_a
    ):
        """Being who the school calls about a child is not being in the room."""
        from datetime import time as time_of_day

        from apps.academic.models import Subject, TimetableSlot, Weekday
        from conftest import _authenticated_as, _make_user

        _make_user(TENANT_A["schema"], "profe.ajeno@alpha.test", "teacher")
        with schema_context(TENANT_A["schema"]):
            from apps.users.models import User

            somebody_else = User.objects.get(email="profe.ajeno@alpha.test")
            # `group_a`'s tutor is `teacher_a`; this class is somebody else's.
            other_subject = Subject.objects.create(
                code="HIS", name="Historia", program=program_a, teacher=somebody_else
            )
            slot = TimetableSlot.objects.create(
                group=group_a,
                subject=other_subject,
                weekday=Weekday.MONDAY,
                start_time=time_of_day(10, 0),
                end_time=time_of_day(11, 0),
            )

        tutor = _authenticated_as("teacher@alpha.test")
        response = _take(
            tutor, slot, A_MONDAY, [{"enrollment_id": str(enrollment_a.id), "status": "absent"}]
        )

        assert response.status_code == 403

    def test_a_student_sees_no_register(self, as_student_a, slot_a):
        assert (
            as_student_a.get(
                ROLL, {"slot": str(slot_a.id), "date": A_MONDAY.isoformat()}
            ).status_code
            == 403
        )


class TestTheDaysClasses:
    def test_it_says_which_registers_are_still_missing(self, as_admin_a, slot_today, enrollment_a):
        """The whole point of the screen, answered without a request per row."""
        body = as_admin_a.get(TODAY_CLASSES).data
        assert [item["session"] for item in body] == [None]

        _take(
            as_admin_a,
            slot_today,
            timezone.localdate(),
            [{"enrollment_id": str(enrollment_a.id), "status": "present"}],
        )

        body = as_admin_a.get(TODAY_CLASSES).data
        assert body[0]["session"]["status"] == "held"


class TestTheTrend:
    def test_late_counts_as_attended_and_excused_does_not(
        self, as_admin_a, slot_today, enrollment_a, program_a, academic_year_a, group_a, tenant_a
    ):
        """An excused absence is justified, but the child was still not there."""
        from apps.academic.models import Enrollment, EnrollmentStatus
        from apps.users.models import User, UserRole

        with schema_context(TENANT_A["schema"]):
            second = User.objects.create_user(
                email="segunda@alpha.test", password="x", role=UserRole.STUDENT, last_name="Bravo"
            )
            other = Enrollment.objects.create(
                student=second,
                program=program_a,
                academic_year=academic_year_a,
                group=group_a,
                status=EnrollmentStatus.ACTIVE,
                enrolled_on=academic_year_a.start_date,
            )

        _take(
            as_admin_a,
            slot_today,
            timezone.localdate(),
            [
                {"enrollment_id": str(enrollment_a.id), "status": "late"},
                {"enrollment_id": str(other.id), "status": "excused"},
            ],
        )

        today = as_admin_a.get(WEEKLY).data[-1]
        assert today["recorded"] == 2
        assert today["value"] == 50.0

    def test_a_day_with_no_register_is_not_zero_per_cent(self, as_admin_a, slot_today):
        """It is a day nobody took a roll, and the client must be able to tell."""
        series = as_admin_a.get(WEEKLY).data

        assert len(series) == 7
        assert all(point["recorded"] == 0 for point in series)

    def test_a_cancelled_class_does_not_drag_the_rate_down(
        self, as_admin_a, slot_today, enrollment_a
    ):
        _take(as_admin_a, slot_today, timezone.localdate(), [], status="cancelled")

        assert as_admin_a.get(WEEKLY).data[-1]["recorded"] == 0


class TestTheModuleSwitch:
    def test_attendance_goes_with_the_timetable(self, as_admin_a, slot_a):
        """Switching off the timetable leaves nothing to take a roll against."""
        query = {"slot": str(slot_a.id), "date": A_MONDAY.isoformat()}
        assert as_admin_a.get(ROLL, query).status_code == 200

        with tenant_setting(TENANT_A["schema"], disabled_modules=["schedule"]):
            response = as_admin_a.get(ROLL, query)

        assert response.status_code == 403
        assert response.data["error"]["code"] == "module_disabled"

    def test_attendance_can_be_switched_off_on_its_own(self, as_admin_a, slot_a):
        """The timetable stays; only the register goes."""
        with tenant_setting(TENANT_A["schema"], disabled_modules=["attendance"]):
            assert as_admin_a.get("/api/v1/academic/timetable/").status_code == 200
            assert (
                as_admin_a.get(
                    ROLL, {"slot": str(slot_a.id), "date": A_MONDAY.isoformat()}
                ).status_code
                == 403
            )
