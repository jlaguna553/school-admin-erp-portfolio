"""
The academic context's public interface for *other* bounded contexts.

Rule A.2: distant modules must not reach into each other's ORM. Billing needs to
know a few facts about an enrollment (who, which programme, is it active) but it
must not import :class:`apps.academic.models.Enrollment` or join against it.

Instead it calls the functions here, which return plain dataclasses. When the
academic context is eventually extracted into its own service, only this module
changes -- an HTTP or message-bus call replaces the ORM query and every caller
keeps working.
"""

from dataclasses import dataclass
from uuid import UUID

from .models import Enrollment, EnrollmentStatus


@dataclass(frozen=True, slots=True)
class EnrollmentSnapshot:
    """An immutable, transport-agnostic view of an enrollment."""

    enrollment_id: UUID
    student_id: UUID
    student_full_name: str
    program_id: UUID
    program_code: str
    program_name: str
    academic_year_id: UUID
    academic_year_name: str
    status: str

    @property
    def is_billable(self) -> bool:
        return self.status in {EnrollmentStatus.ACTIVE, EnrollmentStatus.PENDING}


def _to_snapshot(enrollment: Enrollment) -> EnrollmentSnapshot:
    return EnrollmentSnapshot(
        enrollment_id=enrollment.id,
        student_id=enrollment.student_id,
        student_full_name=enrollment.student.get_full_name(),
        program_id=enrollment.program_id,
        program_code=enrollment.program.code,
        program_name=enrollment.program.name,
        academic_year_id=enrollment.academic_year_id,
        academic_year_name=enrollment.academic_year.name,
        status=enrollment.status,
    )


def get_enrollment_snapshot(enrollment_id: UUID) -> EnrollmentSnapshot | None:
    """Look up one enrollment. Returns ``None`` when it does not exist."""
    enrollment = (
        Enrollment.objects.select_related("student", "program", "academic_year")
        .filter(pk=enrollment_id)
        .first()
    )
    return _to_snapshot(enrollment) if enrollment is not None else None


def get_enrollment_snapshots(enrollment_ids: list[UUID]) -> dict[UUID, EnrollmentSnapshot]:
    """Batch variant, so callers never issue a query per row."""
    enrollments = Enrollment.objects.select_related("student", "program", "academic_year").filter(
        pk__in=enrollment_ids
    )
    return {e.id: _to_snapshot(e) for e in enrollments}


def enrollment_exists_and_is_billable(enrollment_id: UUID) -> bool:
    """Cheap validation hook used by billing before it issues an invoice."""
    return Enrollment.objects.filter(
        pk=enrollment_id,
        status__in=(EnrollmentStatus.ACTIVE, EnrollmentStatus.PENDING),
    ).exists()
