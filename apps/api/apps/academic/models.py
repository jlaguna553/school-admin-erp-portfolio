"""
The academic bounded context: what is taught, when, and to whom.

Every model here lives in the school's own schema, so no model carries a tenant
column. Names and descriptions that a school publishes to families are
translatable (see ``translation.py``) -- registration codes are not.
"""

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class AcademicYear(BaseModel):
    """A school year, e.g. 2026-2027."""

    name = models.CharField(max_length=64, verbose_name=_("name"))
    start_date = models.DateField(verbose_name=_("start date"))
    end_date = models.DateField(verbose_name=_("end date"))
    is_current = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("current"),
        help_text=_("Exactly one academic year should be current at a time."),
    )

    class Meta:
        verbose_name = _("academic year")
        verbose_name_plural = _("academic years")
        ordering = ("-start_date",)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="academic_year_end_after_start",
            ),
        )

    def __str__(self) -> str:
        return self.name


class Program(BaseModel):
    """A degree programme / grade level. ``name`` and ``description`` translate."""

    code = models.CharField(max_length=32, unique=True, verbose_name=_("code"))
    name = models.CharField(max_length=200, verbose_name=_("name"))
    description = models.TextField(blank=True, verbose_name=_("description"))

    class Meta:
        verbose_name = _("programme")
        verbose_name_plural = _("programmes")
        ordering = ("code",)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class Subject(BaseModel):
    """A subject taught within a programme. ``name`` and ``description`` translate."""

    code = models.CharField(max_length=32, verbose_name=_("code"))
    name = models.CharField(max_length=200, verbose_name=_("name"))
    description = models.TextField(blank=True, verbose_name=_("description"))
    credits = models.PositiveSmallIntegerField(
        default=1,
        validators=(MinValueValidator(1), MaxValueValidator(100)),
        verbose_name=_("credits"),
    )
    # Same bounded context -> a real ForeignKey is correct here.
    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name="subjects",
        verbose_name=_("programme"),
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subjects_taught",
        verbose_name=_("teacher"),
    )

    class Meta:
        verbose_name = _("subject")
        verbose_name_plural = _("subjects")
        ordering = ("program__code", "code")
        constraints = (
            models.UniqueConstraint(
                fields=("program", "code"),
                condition=models.Q(deleted_at__isnull=True),
                name="subject_code_unique_per_program",
            ),
        )

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class StudentGroup(BaseModel):
    """A section of a programme that is taught together -- "1º A".

    The concept the timetable and the roll both need. A programme says *what* a
    student studies; a group says *with whom and in which room*, and a class
    session is a group meeting a subject at an hour. Without it, "take the roll
    for this class" has no roster to take it against.

    ``tutor`` is the homeroom teacher, recorded because a group is the unit a
    school calls about a student. It confers nothing: who may take the roll is
    decided by the subject being taught, not by the group.
    """

    name = models.CharField(max_length=64, verbose_name=_("name"))
    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name="groups",
        verbose_name=_("programme"),
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="groups",
        verbose_name=_("academic year"),
    )
    tutor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tutored_groups",
        verbose_name=_("tutor"),
    )
    room = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_("home room"),
        help_text=_("Where the group is by default. A timetable entry may override it."),
    )

    class Meta:
        verbose_name = _("group")
        verbose_name_plural = _("groups")
        ordering = ("academic_year__start_date", "program__code", "name")
        constraints = (
            models.UniqueConstraint(
                fields=("program", "academic_year", "name"),
                condition=models.Q(deleted_at__isnull=True),
                name="group_unique_name_per_program_and_year",
            ),
        )

    def __str__(self) -> str:
        return f"{self.program.code} {self.name}"


class EnrollmentStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    ACTIVE = "active", _("Active")
    WITHDRAWN = "withdrawn", _("Withdrawn")
    COMPLETED = "completed", _("Completed")


class Enrollment(BaseModel):
    """A student enrolled in a programme for an academic year.

    ``student`` is a ForeignKey because identity lives in the same schema and the
    same aggregate boundary. Billing, by contrast, only ever stores this row's
    UUID -- see :mod:`apps.billing.models`.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="enrollments",
        verbose_name=_("student"),
    )
    program = models.ForeignKey(
        Program,
        on_delete=models.PROTECT,
        related_name="enrollments",
        verbose_name=_("programme"),
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="enrollments",
        verbose_name=_("academic year"),
    )
    # The group lives on the enrolment rather than in a membership table of its
    # own: a student enrolled in a programme for a year sits in exactly one of
    # its sections, so a second table would only give two places to disagree.
    #
    # Nullable, and that is not a formality. Schools that do not stream their
    # students keep working untouched, and every enrolment recorded before
    # groups existed stays valid instead of needing a group invented for it.
    group = models.ForeignKey(
        StudentGroup,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="enrollments",
        verbose_name=_("group"),
    )
    status = models.CharField(
        max_length=16,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.PENDING,
        db_index=True,
        verbose_name=_("status"),
    )
    enrolled_on = models.DateField(verbose_name=_("enrolled on"))

    class Meta:
        verbose_name = _("enrollment")
        verbose_name_plural = _("enrollments")
        ordering = ("-enrolled_on",)
        constraints = (
            models.UniqueConstraint(
                fields=("student", "program", "academic_year"),
                condition=models.Q(deleted_at__isnull=True),
                name="enrollment_unique_student_program_year",
            ),
        )

    def __str__(self) -> str:
        return f"{self.student.get_full_name()} · {self.program.code}"


class Term(BaseModel):
    """An evaluation period inside an academic year -- a trimester, a semester.

    Grades hang off a term rather than off the year directly, because a report
    card is a statement about a period: "this is where the student stood in
    November", not an average that silently rewrites itself all year.
    """

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="terms",
        verbose_name=_("academic year"),
    )
    name = models.CharField(max_length=64, verbose_name=_("name"))
    # Explicit rather than inferred from the dates: a school may run overlapping
    # or non-contiguous periods, and "first" is a label the school owns.
    ordinal = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_("position"),
        help_text=_("Order within the year. Report cards are printed in this order."),
    )
    start_date = models.DateField(verbose_name=_("start date"))
    end_date = models.DateField(verbose_name=_("end date"))
    is_current = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("current"),
        help_text=_("The period the gradebook opens on."),
    )

    class Meta:
        verbose_name = _("evaluation period")
        verbose_name_plural = _("evaluation periods")
        ordering = ("academic_year__start_date", "ordinal")
        constraints = (
            models.UniqueConstraint(
                fields=("academic_year", "ordinal"),
                condition=models.Q(deleted_at__isnull=True),
                name="term_unique_ordinal_per_year",
            ),
        )

    def __str__(self) -> str:
        return f"{self.name} · {self.academic_year.name}"


class Assessment(BaseModel):
    """Something a student is graded on: an exam, a project, participation.

    ``max_score`` is per assessment rather than per school because the two
    genuinely differ -- an exam out of 100 and homework out of 10 sit in the
    same term. Averages therefore normalise before weighting, so a 9/10 counts
    as 0.9 next to an 85/100 counting as 0.85, instead of the exam dominating by
    virtue of its scale.
    """

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="assessments",
        verbose_name=_("subject"),
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        related_name="assessments",
        verbose_name=_("evaluation period"),
    )
    name = models.CharField(max_length=200, verbose_name=_("name"))
    max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name=_("maximum score"),
    )
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("weight"),
        help_text=_("Relative to the other assessments in the same period."),
    )
    due_date = models.DateField(null=True, blank=True, verbose_name=_("due date"))

    class Meta:
        verbose_name = _("assessment")
        verbose_name_plural = _("assessments")
        ordering = ("term__ordinal", "due_date", "name")

    def __str__(self) -> str:
        return f"{self.name} · {self.subject.code}"


class Grade(BaseModel):
    """One student's score on one assessment.

    Keyed on the *enrollment* rather than the student: that is what ties the
    score to a programme and a year, and it makes it impossible to grade someone
    who is not enrolled in the programme the subject belongs to. Grading a
    student twice for the same assessment is refused by the database, not by a
    check somebody can forget.
    """

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="grades",
        verbose_name=_("assessment"),
    )
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.PROTECT,
        related_name="grades",
        verbose_name=_("enrollment"),
    )
    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("score"),
    )
    comment = models.CharField(max_length=300, blank=True, verbose_name=_("comment"))

    # Who last touched it. A grade is a claim about a person's work, so the
    # record of who made the claim is part of the record.
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_grades",
        verbose_name=_("recorded by"),
    )

    class Meta:
        verbose_name = _("grade")
        verbose_name_plural = _("grades")
        ordering = ("assessment__term__ordinal", "assessment__name")
        constraints = (
            models.UniqueConstraint(
                fields=("assessment", "enrollment"),
                condition=models.Q(deleted_at__isnull=True),
                name="grade_unique_per_assessment_and_enrollment",
            ),
        )

    def __str__(self) -> str:
        return (
            f"{self.enrollment.student.get_full_name()}: {self.score}/{self.assessment.max_score}"
        )

    @property
    def ratio(self) -> Decimal:
        """The score normalised to 0..1, so scales can be compared."""
        if self.assessment.max_score <= 0:  # pragma: no cover -- validator forbids it
            return Decimal("0")
        return self.score / self.assessment.max_score


class Weekday(models.IntegerChoices):
    """ISO-8601 numbering, so ``date.isoweekday()`` is the value.

    Not Django's own ``0 = Sunday``: every check here compares a slot against a
    real date, and a numbering that needs converting first is a bug waiting for
    the one place somebody forgets.
    """

    MONDAY = 1, _("Monday")
    TUESDAY = 2, _("Tuesday")
    WEDNESDAY = 3, _("Wednesday")
    THURSDAY = 4, _("Thursday")
    FRIDAY = 5, _("Friday")
    SATURDAY = 6, _("Saturday")
    SUNDAY = 7, _("Sunday")


class TimetableSlot(BaseModel):
    """A recurring weekly class: this group, this subject, this hour.

    The timetable is stored as the weekly pattern, not as every meeting of the
    year. Materialising ~40 dates per slot up front would mean a year's worth of
    rows to rewrite every time a school moves a class an hour later -- and
    schools do that in the first month. Individual meetings become rows only
    when something is recorded about them: see :class:`ClassSession`.
    """

    group = models.ForeignKey(
        StudentGroup,
        on_delete=models.CASCADE,
        related_name="slots",
        verbose_name=_("group"),
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="slots",
        verbose_name=_("subject"),
    )
    weekday = models.PositiveSmallIntegerField(
        choices=Weekday.choices,
        db_index=True,
        verbose_name=_("weekday"),
    )
    start_time = models.TimeField(verbose_name=_("starts at"))
    end_time = models.TimeField(verbose_name=_("ends at"))
    room = models.CharField(max_length=64, blank=True, verbose_name=_("room"))

    class Meta:
        verbose_name = _("timetable entry")
        verbose_name_plural = _("timetable entries")
        ordering = ("weekday", "start_time")
        constraints = (
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="timetable_slot_ends_after_start",
            ),
        )

    def __str__(self) -> str:
        return f"{self.group} · {self.subject.code} · {self.get_weekday_display()}"

    def overlaps(self, start: Any, end: Any) -> bool:
        """Half-open comparison, so a class ending at 09:00 frees 09:00."""
        return self.start_time < end and start < self.end_time


class SessionStatus(models.TextChoices):
    HELD = "held", _("Held")
    CANCELLED = "cancelled", _("Cancelled")


class ClassSession(BaseModel):
    """One actual meeting of a timetable slot, on one date.

    Exists so that "nobody was marked absent" and "nobody took the roll" are
    different facts. Attendance hangs off the session, and the session records
    who took it and when -- a register is a claim about where a child was, so
    the claim carries its author.

    A cancelled session is not an absence for the whole class, which is why the
    status lives here rather than being inferred from an empty register.
    """

    slot = models.ForeignKey(
        TimetableSlot,
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name=_("timetable entry"),
    )
    date = models.DateField(db_index=True, verbose_name=_("date"))
    status = models.CharField(
        max_length=16,
        choices=SessionStatus.choices,
        default=SessionStatus.HELD,
        verbose_name=_("status"),
    )
    note = models.CharField(max_length=300, blank=True, verbose_name=_("note"))
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rolls_taken",
        verbose_name=_("taken by"),
    )
    taken_at = models.DateTimeField(null=True, blank=True, verbose_name=_("taken at"))

    class Meta:
        verbose_name = _("class session")
        verbose_name_plural = _("class sessions")
        ordering = ("-date", "slot__start_time")
        constraints = (
            models.UniqueConstraint(
                fields=("slot", "date"),
                condition=models.Q(deleted_at__isnull=True),
                name="class_session_unique_per_slot_and_date",
            ),
        )

    def __str__(self) -> str:
        return f"{self.slot} · {self.date}"


class AttendanceStatus(models.TextChoices):
    PRESENT = "present", _("Present")
    LATE = "late", _("Late")
    ABSENT = "absent", _("Absent")
    EXCUSED = "excused", _("Excused")


class Attendance(BaseModel):
    """One student's mark in one class session.

    Keyed on the *enrollment*, like :class:`Grade` and for the same reason: it
    ties the record to a programme and a year, and makes it impossible to mark
    somebody who is not enrolled.

    There is no row for a student who has not been marked. An absence is a
    statement somebody made, and defaulting every unmarked student to *present*
    would manufacture attendance records for a roll nobody took.
    """

    session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE,
        related_name="records",
        verbose_name=_("class session"),
    )
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.PROTECT,
        related_name="attendance",
        verbose_name=_("enrollment"),
    )
    status = models.CharField(
        max_length=16,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
        db_index=True,
        verbose_name=_("status"),
    )
    note = models.CharField(max_length=300, blank=True, verbose_name=_("note"))

    class Meta:
        verbose_name = _("attendance record")
        verbose_name_plural = _("attendance records")
        ordering = ("session__date", "enrollment__student__last_name")
        constraints = (
            models.UniqueConstraint(
                fields=("session", "enrollment"),
                condition=models.Q(deleted_at__isnull=True),
                name="attendance_unique_per_session_and_enrollment",
            ),
        )

    def __str__(self) -> str:
        return f"{self.enrollment.student.get_full_name()}: {self.get_status_display()}"
