"""Who may record a mark, and who may take the roll."""

from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.users.models import UserRole


class TeachesThisSubject(BasePermission):
    """A teacher writes marks for their own subjects; nobody else's.

    The module permission already decided that teachers belong in the gradebook
    at all. This narrows it to the only defensible scope: the subjects they are
    assigned to teach. Without it any teacher in the school could alter any
    other teacher's marks, which is a claim about a student's work that the
    record would then attribute to the wrong person.

    Coordinators and administrators are exempt. Somebody has to be able to
    correct a mark after a teacher has left, and that is the job the ladder in
    :mod:`apps.core.roles` puts above them.
    """

    message = "You can only record marks for subjects you teach."

    #: Roles that may act on any subject in the school.
    OVERSIGHT = (UserRole.SCHOOL_ADMIN, UserRole.COORDINATOR)

    def has_permission(self, request: Request, view: APIView) -> bool:
        # Reads are already scoped by the module permission; the narrowing is
        # about who may *change* a mark.
        return True

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if getattr(user, "role", None) in self.OVERSIGHT:
            return True

        subject = self.subject_of(obj)
        return subject is not None and subject.teacher_id == user.pk

    @staticmethod
    def subject_of(obj: Any) -> Any:
        """The subject an assessment, a grade or a timetabled class belongs to."""
        if hasattr(obj, "subject_id"):
            return obj.subject
        if hasattr(obj, "assessment"):
            return obj.assessment.subject
        if hasattr(obj, "slot"):
            return obj.slot.subject
        return None


def teaches(user: Any, subject: Any) -> bool:
    """The rule itself, for the endpoints with no object to hook on to.

    One rule, two names below, because the two acts read differently at the call
    site and are refused with different messages -- but "the teacher of record,
    or somebody above them" is the same answer to both.
    """
    if getattr(user, "role", None) in TeachesThisSubject.OVERSIGHT:
        return True
    return subject is not None and subject.teacher_id == user.pk


def may_grade_subject(user: Any, subject: Any) -> bool:
    return teaches(user, subject)


def may_take_roll(user: Any, slot: Any) -> bool:
    """The roll belongs to whoever is teaching the class.

    Not to the group's tutor: a tutor is who the school calls about a student,
    which is a different question from who was standing in the room at ten past
    nine. Oversight roles keep their exemption -- somebody has to be able to fix
    a register after the teacher has gone home.
    """
    return teaches(user, slot.subject)
