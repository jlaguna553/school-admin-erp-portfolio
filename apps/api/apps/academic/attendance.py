"""
Taking the roll, and reading it back.

Two decisions run through this module.

**An unmarked student has no record.** The register returns ``status: null`` for
anyone nobody has marked, and saving writes every row explicitly. The tempting
shortcut -- default everyone to present and store only the absentees -- makes
"the teacher marked them present" and "nobody took the roll" the same row, which
is precisely the distinction a parent is asking about when they call.

**The rate counts present and late as attended, and excused as absent.** An
excused absence is a justified absence: the justification belongs in the record
and in the conversation with the family, but the child was not in the room, and
a rate that says otherwise cannot be used to spot a child who is missing school.
"""

from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from typing import Any

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from .models import (
    Attendance,
    AttendanceStatus,
    ClassSession,
    Enrollment,
    EnrollmentStatus,
    SessionStatus,
    TimetableSlot,
)

#: What counts towards the attendance rate. See the module docstring.
ATTENDED = (AttendanceStatus.PRESENT, AttendanceStatus.LATE)


@dataclass(frozen=True)
class RollRow:
    """One student's line in the register."""

    enrollment_id: Any
    student_id: Any
    student_name: str
    #: ``None`` until somebody marks them -- distinct from being marked absent.
    status: str | None
    note: str


def roster_for(slot: TimetableSlot) -> QuerySet[Enrollment]:
    """The students who should be in that room.

    The group's members, not the programme's. A programme-wide roster would put
    every section of the year in front of a teacher who is looking at one of
    them, and a register nobody can read through is a register nobody takes.
    """
    return (
        Enrollment.objects.filter(
            group_id=slot.group_id,
            status__in=(EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED),
        )
        .select_related("student")
        .order_by("student__last_name", "student__first_name")
    )


def session_for(slot: TimetableSlot, on: date_type) -> ClassSession | None:
    """The register for that meeting, if one has been opened."""
    return ClassSession.objects.filter(slot=slot, date=on).first()


def build(slot: TimetableSlot, on: date_type) -> tuple[ClassSession | None, list[RollRow]]:
    """The register: every student in the group, with whatever is recorded."""
    session = session_for(slot, on)
    marks: dict[Any, Attendance] = {}
    if session is not None:
        marks = {record.enrollment_id: record for record in session.records.all()}

    rows = []
    for enrollment in roster_for(slot):
        mark = marks.get(enrollment.id)
        rows.append(
            RollRow(
                enrollment_id=enrollment.id,
                student_id=enrollment.student_id,
                student_name=enrollment.student.get_full_name(),
                status=mark.status if mark else None,
                note=mark.note if mark else "",
            )
        )
    return session, rows


def record(
    *,
    slot: TimetableSlot,
    on: date_type,
    entries: list[dict],
    taken_by: Any,
    session_status: str = SessionStatus.HELD,
    note: str = "",
) -> ClassSession:
    """Write the register for one meeting.

    The whole register in one call, because that is one act: a teacher looks up
    once and marks the room. Saving student by student would make a half-taken
    roll the ordinary result of a dropped connection, and a half-taken roll
    reads exactly like a class where half the students were absent.

    Cancelling clears the marks. A class that did not happen cannot leave
    absences behind it -- those absences would be counted against students for a
    lesson nobody gave.
    """
    from django.db import transaction

    with transaction.atomic():
        session, _created = ClassSession.objects.update_or_create(
            slot=slot,
            date=on,
            defaults={
                "status": session_status,
                "note": note,
                "taken_by": taken_by,
                "taken_at": timezone.now(),
                "is_active": True,
                "deleted_at": None,
            },
        )

        if session_status == SessionStatus.CANCELLED:
            Attendance.all_objects.filter(session=session).delete()
            return session

        valid = {enrollment.id: enrollment for enrollment in roster_for(slot)}
        for entry in entries:
            enrollment = valid.get(entry["enrollment_id"])
            if enrollment is None:
                # A stale row in the client's copy of the register -- somebody
                # moved between groups while the sheet was open. Ignored rather
                # than rejected: it can only ever name a student who is not in
                # this room, which is the case the filter exists to stop.
                continue

            status = entry.get("status")
            if status is None:
                Attendance.all_objects.filter(session=session, enrollment=enrollment).delete()
                continue

            Attendance.objects.update_or_create(
                session=session,
                enrollment=enrollment,
                defaults={
                    "status": status,
                    "note": entry.get("note", ""),
                    "is_active": True,
                    "deleted_at": None,
                },
            )

    return session


def daily_rates(*, days: int = 7, until: date_type | None = None) -> list[dict]:
    """Attendance rate per day, oldest first.

    A trailing window rather than the current Monday-to-Sunday week: asked on a
    Wednesday, the calendar week is more than half empty, and a chart that is
    mostly blank says nothing about whether attendance is slipping.

    Days with no register come back with ``recorded: 0``. They are not zero per
    cent -- they are days nobody took a roll, most often a weekend or a holiday,
    and the interface drops them instead of plotting a cliff.
    """
    end = until or timezone.localdate()
    start = end - timedelta(days=days - 1)

    counted = (
        Attendance.objects.filter(
            session__date__range=(start, end),
            # A cancelled class is not a day of poor attendance.
            session__status=SessionStatus.HELD,
        )
        .values("session__date")
        .annotate(
            recorded=Count("id"),
            attended=Count("id", filter=Q(status__in=ATTENDED)),
        )
    )
    by_date = {row["session__date"]: row for row in counted}

    series = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        row = by_date.get(day)
        recorded = row["recorded"] if row else 0
        attended = row["attended"] if row else 0
        series.append(
            {
                "date": day,
                "recorded": recorded,
                "value": round(attended * 100 / recorded, 1) if recorded else 0.0,
            }
        )
    return series
