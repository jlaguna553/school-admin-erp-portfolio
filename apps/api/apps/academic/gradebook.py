"""
The gradebook: one subject, one period, every enrolled student.

Kept apart from :mod:`apps.academic.services`, which exists to answer the
*billing* context's questions across a boundary. This is internal to academic
and free to traverse the ORM.

The only real calculation here is the period average, and it is worth stating
plainly because it is the number families argue about. Scores are normalised
before they are weighted: an exam out of 100 and homework out of 10 sit in the
same period, so a raw sum would let the exam dominate purely because its scale
is larger. Each score becomes a ratio of its own maximum, and the ratios are
weighted.

Ungraded assessments are **excluded** rather than counted as zero. Mid-period,
most assessments have no grade yet, and treating those as zeros would show every
student failing until the last exam was marked -- a number nobody could act on.
The cost is that an average is over what has been graded so far, which is the
honest reading and is labelled as such in the interface.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet

from .models import Assessment, Enrollment, EnrollmentStatus, Grade, Subject, Term


@dataclass(frozen=True)
class StudentRow:
    """One student's line in the gradebook."""

    enrollment_id: Any
    student_id: Any
    student_name: str
    #: assessment id -> score
    scores: dict[Any, Decimal]
    average: Decimal | None
    graded_count: int


def assessments_for(subject: Subject, term: Term) -> QuerySet[Assessment]:
    return Assessment.objects.filter(subject=subject, term=term).order_by("due_date", "name")


def enrollments_for(subject: Subject, term: Term) -> QuerySet[Enrollment]:
    """Students who should appear, in a stable order.

    Restricted to the subject's programme and the period's year -- a subject
    belongs to one programme, and a gradebook that listed the whole school would
    be unusable. Withdrawn enrolments are dropped: they are not being taught.
    """
    return (
        Enrollment.objects.filter(
            program=subject.program,
            academic_year=term.academic_year,
            status__in=(EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED),
        )
        .select_related("student")
        .order_by("student__last_name", "student__first_name")
    )


def average_scale(assessments: list[Assessment]) -> Decimal:
    """The scale to report a period average on.

    When every assessment is marked out of the same maximum -- the ordinary
    case, a school that marks everything out of 10 -- the average is reported on
    that scale, because that is the number a teacher is expecting to read.

    When they differ there is no natural scale, so it falls back to a
    percentage. An earlier version took the scale from whichever assessment
    happened to sort first, which meant adding a homework marked out of 10 could
    silently redraw every average in the period onto a different scale.
    """
    maxima = {assessment.max_score for assessment in assessments}
    if len(maxima) == 1:
        return maxima.pop()
    return Decimal("100")


def weighted_average(
    scores: dict[Any, Decimal], assessments: list[Assessment]
) -> tuple[Decimal | None, int]:
    """Average of what has been graded, normalised then weighted.

    Returns ``(None, 0)`` when nothing is graded yet, rather than zero: "no mark"
    and "a mark of zero" are different claims about a student and must not
    render the same.
    """
    total_weight = Decimal("0")
    accumulated = Decimal("0")
    graded = 0

    for assessment in assessments:
        score = scores.get(assessment.id)
        if score is None:
            continue
        graded += 1
        if assessment.max_score <= 0:  # pragma: no cover -- validators forbid it
            continue
        ratio = Decimal(score) / assessment.max_score
        accumulated += ratio * assessment.weight
        total_weight += assessment.weight

    if graded == 0 or total_weight == 0:
        return None, graded

    scale = average_scale(assessments)
    return (accumulated / total_weight * scale).quantize(Decimal("0.01")), graded


def build(subject: Subject, term: Term) -> tuple[list[Assessment], list[StudentRow]]:
    """The whole grid, in two queries plus one for the grades."""
    assessments = list(assessments_for(subject, term))
    enrollments = list(enrollments_for(subject, term))

    grades = Grade.objects.filter(
        assessment__in=assessments, enrollment__in=enrollments
    ).values_list("enrollment_id", "assessment_id", "score")

    by_enrollment: dict[Any, dict[Any, Decimal]] = {}
    for enrollment_id, assessment_id, score in grades:
        by_enrollment.setdefault(enrollment_id, {})[assessment_id] = score

    rows = []
    for enrollment in enrollments:
        scores = by_enrollment.get(enrollment.id, {})
        average, graded = weighted_average(scores, assessments)
        rows.append(
            StudentRow(
                enrollment_id=enrollment.id,
                student_id=enrollment.student_id,
                student_name=enrollment.student.get_full_name(),
                scores=scores,
                average=average,
                graded_count=graded,
            )
        )

    return assessments, rows


def record(*, assessment: Assessment, entries: list[dict], recorded_by: Any) -> list[Grade]:
    """Write a column of marks, replacing whatever was there.

    Each entry names an enrollment and a score. A ``None`` score **clears** the
    mark rather than storing zero: "not marked" and "marked zero" are different
    claims about a student, and collapsing them would silently fail people who
    simply have not been graded yet.

    Enrollments that do not belong to this assessment's subject are ignored
    rather than rejected, so one stale row in a client's cached grid cannot fail
    the whole column. Marks are keyed to the enrollment, so a wrong id could
    only ever write to a student who is not in the class -- which is exactly
    what the filter prevents.
    """
    from django.db import transaction

    valid = {
        enrollment.id: enrollment
        for enrollment in enrollments_for(assessment.subject, assessment.term)
    }

    written: list[Grade] = []
    with transaction.atomic():
        for entry in entries:
            enrollment = valid.get(entry["enrollment_id"])
            if enrollment is None:
                continue

            score = entry.get("score")
            if score is None:
                Grade.objects.filter(assessment=assessment, enrollment=enrollment).delete()
                continue

            grade, _created = Grade.objects.update_or_create(
                assessment=assessment,
                enrollment=enrollment,
                defaults={
                    "score": min(score, assessment.max_score),
                    "comment": entry.get("comment", ""),
                    "recorded_by": recorded_by,
                    "is_active": True,
                    "deleted_at": None,
                },
            )
            written.append(grade)

    return written
