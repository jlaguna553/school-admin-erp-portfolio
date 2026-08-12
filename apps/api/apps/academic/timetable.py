"""
The weekly timetable, and the three ways of double-booking it.

A timetable is mostly a scheduling-conflict detector with a grid drawn on top.
Three resources can only be in one place at a time, and each produces a
different mistake with a different fix:

* the **group** -- a class cannot be in two lessons at once;
* the **teacher** -- the clash a timetable is actually built to avoid, and the
  one nobody notices until two groups are waiting for the same person;
* the **room** -- recorded only when a room is named, since a blank room means
  "unspecified", not "the room called empty string".

None of this is a database constraint. Postgres could express the overlap with
an exclusion constraint over a time range, but soft-deleted rows would keep
holding their slot, and the teacher clash is not on this table at all -- it
crosses a foreign key to the subject. A constraint that catches one of the three
and reports it as a 500 is worse than a check that catches all three and says
which teacher, where.
"""

from dataclasses import dataclass
from datetime import time
from typing import Any

from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _

from .models import ClassSession, StudentGroup, Subject, TimetableSlot, Weekday


@dataclass(frozen=True)
class Clash:
    """A slot that already occupies the requested hour."""

    #: Which resource is taken: ``group``, ``teacher`` or ``room``.
    resource: str
    slot: TimetableSlot
    message: Any


def overlapping(weekday: int, start: time, end: time) -> QuerySet[TimetableSlot]:
    """Every slot on that weekday touching the interval.

    Half-open: a class ending at 09:00 does not clash with one starting at
    09:00, which is how back-to-back periods are timetabled everywhere.
    """
    return TimetableSlot.objects.filter(
        weekday=weekday, start_time__lt=end, end_time__gt=start
    ).select_related("group", "subject", "subject__teacher")


def find_clashes(
    *,
    group: StudentGroup,
    subject: Subject,
    weekday: int,
    start: time,
    end: time,
    room: str = "",
    exclude_pk: Any = None,
) -> list[Clash]:
    """Everything that would be double-booked by this entry.

    All of them, not the first: moving a class to an hour where both the group
    and the teacher are busy is one edit, and being told about one clash at a
    time turns it into two failed attempts.
    """
    candidates = overlapping(weekday, start, end)
    if exclude_pk is not None:
        candidates = candidates.exclude(pk=exclude_pk)

    conditions = Q(group=group)
    if subject.teacher_id:
        conditions |= Q(subject__teacher_id=subject.teacher_id)
    if room:
        conditions |= Q(room__iexact=room)

    clashes: list[Clash] = []
    for other in candidates.filter(conditions):
        if other.group_id == group.pk:
            clashes.append(
                Clash(
                    "group",
                    other,
                    _("%(group)s already has %(subject)s at that hour.")
                    % {"group": str(group), "subject": other.subject.name},
                )
            )
        elif subject.teacher_id and other.subject.teacher_id == subject.teacher_id:
            clashes.append(
                Clash(
                    "teacher",
                    other,
                    _("%(teacher)s is teaching %(group)s at that hour.")
                    % {
                        "teacher": subject.teacher.get_full_name(),
                        "group": str(other.group),
                    },
                )
            )
        else:
            clashes.append(
                Clash(
                    "room",
                    other,
                    _("Room %(room)s is taken by %(group)s at that hour.")
                    % {"room": other.room, "group": str(other.group)},
                )
            )

    return clashes


def slots_on(date: Any, *, teacher: Any = None, group: Any = None) -> QuerySet[TimetableSlot]:
    """The classes that fall on a given date.

    A date, not a weekday, because that is the question being asked -- "what am
    I teaching today" -- and turning one into the other in every caller is how
    the two numbering schemes for weekdays eventually get mixed up.
    """
    slots = TimetableSlot.objects.filter(weekday=date.isoweekday()).select_related(
        "group", "group__program", "subject", "subject__teacher"
    )
    if teacher is not None:
        slots = slots.filter(subject__teacher=teacher)
    if group is not None:
        slots = slots.filter(group=group)
    return slots.order_by("start_time")


def sessions_by_slot(date: Any, slots: list[TimetableSlot]) -> dict[Any, ClassSession]:
    """Which of those classes already have a register, keyed by slot."""
    return {
        session.slot_id: session
        for session in ClassSession.objects.filter(date=date, slot__in=slots)
    }


def weekday_of(date: Any) -> int:
    return Weekday(date.isoweekday()).value
