"""
The weekly timetable, which is mostly a double-booking detector.

Three resources can only be in one place at a time -- the group, the teacher and
the room -- and each clash is a different mistake with a different fix, so each
is pinned separately here. The half-open comparison gets its own test because
back-to-back periods are how every school timetables its day, and an inclusive
comparison would refuse all of them.
"""

from datetime import time

import pytest
from django_tenants.utils import schema_context

from conftest import TENANT_A

pytestmark = pytest.mark.django_db

GROUPS = "/api/v1/academic/groups/"
TIMETABLE = "/api/v1/academic/timetable/"

MONDAY = 1
TUESDAY = 2


def _slot(client, group, subject, *, start="08:00", end="09:00", weekday=MONDAY, room=""):
    return client.post(
        TIMETABLE,
        {
            "group": str(group.id),
            "subject": str(subject.id),
            "weekday": weekday,
            "start_time": start,
            "end_time": end,
            "room": room,
        },
        format="json",
    )


@pytest.fixture
def other_group_a(tenant_a, program_a, academic_year_a):
    from apps.academic.models import StudentGroup

    with schema_context(TENANT_A["schema"]):
        return StudentGroup.objects.create(
            name="B", program=program_a, academic_year=academic_year_a
        )


@pytest.fixture
def other_subject_a(tenant_a, program_a, teacher_a):
    """A second subject taught by the *same* teacher."""
    from apps.academic.models import Subject

    with schema_context(TENANT_A["schema"]):
        return Subject.objects.create(
            code="FIS", name="Física", program=program_a, teacher=teacher_a
        )


class TestGroups:
    def test_a_group_reports_how_many_students_it_holds(self, as_admin_a, group_a, enrollment_a):
        """The list is where somebody decides which group is full."""
        body = as_admin_a.get(GROUPS).data
        row = next(item for item in body["results"] if item["id"] == str(group_a.id))
        assert row["student_count"] == 1

    def test_a_student_cannot_be_put_in_another_programme_s_group(
        self, as_admin_a, enrollment_a, academic_year_a, tenant_a
    ):
        """Otherwise the register would list somebody nobody in the room teaches."""
        from apps.academic.models import Program, StudentGroup

        with schema_context(TENANT_A["schema"]):
            other = Program.objects.create(code="SEC", name_es="Secundaria")
            foreign = StudentGroup.objects.create(
                name="A", program=other, academic_year=academic_year_a
            )

        response = as_admin_a.patch(
            f"/api/v1/academic/enrollments/{enrollment_a.id}/",
            {"group": str(foreign.id)},
            format="json",
        )

        assert response.status_code == 400
        assert "group" in response.data["error"]["details"]


class TestDoubleBooking:
    def test_a_group_cannot_be_in_two_classes_at_once(
        self, as_admin_a, group_a, subject_a, other_subject_a
    ):
        assert _slot(as_admin_a, group_a, subject_a).status_code == 201

        response = _slot(as_admin_a, group_a, other_subject_a, start="08:30", end="09:30")

        assert response.status_code == 400
        assert "group" in response.data["error"]["details"]

    def test_a_teacher_cannot_teach_two_groups_at_once(
        self, as_admin_a, group_a, other_group_a, subject_a, other_subject_a
    ):
        """The clash a timetable exists to catch, and the one nobody spots."""
        assert _slot(as_admin_a, group_a, subject_a).status_code == 201

        response = _slot(as_admin_a, other_group_a, other_subject_a)

        assert response.status_code == 400
        details = response.data["error"]["details"]
        assert "subject" in details

    def test_a_room_cannot_hold_two_classes_at_once(
        self, as_admin_a, group_a, other_group_a, subject_a, tenant_a, program_a
    ):
        from apps.academic.models import Subject

        with schema_context(TENANT_A["schema"]):
            # No teacher, so the only possible clash is the room.
            untaught = Subject.objects.create(code="ART", name="Arte", program=program_a)

        assert _slot(as_admin_a, group_a, subject_a, room="Lab").status_code == 201

        response = _slot(as_admin_a, other_group_a, untaught, room="lab")

        assert response.status_code == 400
        assert "room" in response.data["error"]["details"]

    def test_a_blank_room_is_not_a_room(
        self, as_admin_a, group_a, other_group_a, subject_a, tenant_a, program_a
    ):
        """ "Unspecified" is not a place two classes can collide in."""
        from apps.academic.models import Subject

        with schema_context(TENANT_A["schema"]):
            untaught = Subject.objects.create(code="ART", name="Arte", program=program_a)

        assert _slot(as_admin_a, group_a, subject_a).status_code == 201

        assert _slot(as_admin_a, other_group_a, untaught).status_code == 201

    def test_back_to_back_classes_are_allowed(
        self, as_admin_a, group_a, subject_a, other_subject_a
    ):
        """A class ending at 09:00 frees 09:00 -- or no school could be timetabled."""
        assert _slot(as_admin_a, group_a, subject_a, start="08:00", end="09:00").status_code == 201

        response = _slot(as_admin_a, group_a, other_subject_a, start="09:00", end="10:00")

        assert response.status_code == 201

    def test_another_weekday_is_not_a_clash(self, as_admin_a, group_a, subject_a):
        assert _slot(as_admin_a, group_a, subject_a).status_code == 201

        assert _slot(as_admin_a, group_a, subject_a, weekday=TUESDAY).status_code == 201

    def test_every_clash_is_reported_at_once(
        self, as_admin_a, group_a, other_group_a, subject_a, other_subject_a, program_a, tenant_a
    ):
        """One edit, one list of what is wrong with it -- not one refusal each."""
        from apps.academic.models import Subject

        with schema_context(TENANT_A["schema"]):
            untaught = Subject.objects.create(code="ART", name="Arte", program=program_a)

        # The group is busy at 08:00 with a subject nobody teaches...
        assert _slot(as_admin_a, group_a, untaught).status_code == 201
        # ...and the teacher is busy at 08:00 with another group.
        assert _slot(as_admin_a, other_group_a, subject_a).status_code == 201

        response = _slot(as_admin_a, group_a, other_subject_a)

        details = response.data["error"]["details"]
        assert response.status_code == 400
        assert {"group", "subject"} <= set(details)

    def test_one_conflicting_class_is_reported_once(
        self, as_admin_a, group_a, subject_a, other_subject_a
    ):
        """The group's own class, taught by the same teacher, is a single problem.

        Saying both "1º A is busy" and "the teacher is busy with 1º A" would be
        two sentences about one clash, and the second adds nothing.
        """
        assert _slot(as_admin_a, group_a, subject_a).status_code == 201

        details = _slot(as_admin_a, group_a, other_subject_a).data["error"]["details"]

        assert set(details) == {"group"}

    def test_editing_a_class_does_not_clash_with_itself(self, as_admin_a, group_a, subject_a):
        created = _slot(as_admin_a, group_a, subject_a)

        response = as_admin_a.patch(
            f"{TIMETABLE}{created.data['id']}/", {"room": "Lab"}, format="json"
        )

        assert response.status_code == 200


class TestTheEntryItself:
    def test_a_class_must_end_after_it_starts(self, as_admin_a, group_a, subject_a):
        response = _slot(as_admin_a, group_a, subject_a, start="10:00", end="09:00")

        assert response.status_code == 400
        assert "end_time" in response.data["error"]["details"]

    def test_a_subject_from_another_programme_is_refused(
        self, as_admin_a, group_a, academic_year_a, tenant_a
    ):
        from apps.academic.models import Program, Subject

        with schema_context(TENANT_A["schema"]):
            other = Program.objects.create(code="SEC", name_es="Secundaria")
            foreign = Subject.objects.create(code="QUI", name="Química", program=other)

        response = _slot(as_admin_a, group_a, foreign)

        assert response.status_code == 400
        assert "subject" in response.data["error"]["details"]


class TestWhoSeesTheTimetable:
    def test_a_teacher_can_ask_for_their_own_classes(
        self, as_admin_a, as_teacher_a, group_a, subject_a, teacher_a
    ):
        _slot(as_admin_a, group_a, subject_a)

        body = as_teacher_a.get(TIMETABLE, {"teacher": str(teacher_a.id)}).data

        assert body["count"] == 1
        assert body["results"][0]["teacher_name"] == teacher_a.get_full_name()

    def test_a_teacher_does_not_write_the_timetable(self, as_teacher_a, group_a, subject_a):
        """Reading it is their job; building it is the school's."""
        response = _slot(as_teacher_a, group_a, subject_a)

        assert response.status_code == 403

    def test_a_student_sees_nothing_of_it(self, as_student_a):
        assert as_student_a.get(TIMETABLE).status_code == 403


class TestSlotModel:
    def test_overlap_is_half_open(self, tenant_a, slot_a):
        with schema_context(TENANT_A["schema"]):
            assert slot_a.overlaps(time(8, 30), time(9, 30)) is True
            assert slot_a.overlaps(time(9, 0), time(10, 0)) is False
            assert slot_a.overlaps(time(7, 0), time(8, 0)) is False
