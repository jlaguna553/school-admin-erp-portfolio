from datetime import date as date_type
from typing import Any

import django_filters
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.modules import Module
from apps.core.permissions import ModulePermission
from apps.core.viewsets import SoftDeleteModelViewSet

from . import attendance, gradebook
from .models import (
    AcademicYear,
    Assessment,
    Enrollment,
    EnrollmentStatus,
    Program,
    StudentGroup,
    Subject,
    Term,
    TimetableSlot,
)
from .permissions import TeachesThisSubject, may_grade_subject, may_take_roll
from .serializers import (
    AcademicYearSerializer,
    AssessmentSerializer,
    AttendancePointSerializer,
    ClassSessionSerializer,
    EnrollmentSerializer,
    GradebookSerializer,
    GradeInputSerializer,
    GradeSerializer,
    ProgramSerializer,
    ProgramTranslationsSerializer,
    RollInputSerializer,
    RollSerializer,
    StudentGroupSerializer,
    SubjectSerializer,
    TermSerializer,
    TimetableSlotSerializer,
)


class AcademicYearViewSet(SoftDeleteModelViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    permission_classes = (ModulePermission,)
    module = Module.ACADEMIC
    filterset_fields = ("is_current", "is_active")
    ordering_fields = ("start_date", "name")


@extend_schema_view(
    list=extend_schema(
        summary="List programmes",
        description=(
            "``name`` and ``description`` are returned in the language resolved "
            "for the request. Send ``Accept-Language: en`` for English."
        ),
    )
)
class ProgramViewSet(SoftDeleteModelViewSet):
    queryset = Program.objects.all()
    permission_classes = (ModulePermission,)
    module = Module.ACADEMIC
    filterset_fields = ("is_active",)
    search_fields = ("code", "name_es", "name_en")
    ordering_fields = ("code", "name")

    def get_serializer_class(self) -> type[Any]:
        # ``?translations=all`` exposes every language column for admin editors.
        if self.request.query_params.get("translations") == "all":
            return ProgramTranslationsSerializer
        return ProgramSerializer


class SubjectViewSet(SoftDeleteModelViewSet):
    queryset = Subject.objects.select_related("program", "teacher")
    serializer_class = SubjectSerializer
    permission_classes = (ModulePermission,)
    module = Module.SUBJECTS
    filterset_fields = ("program", "teacher", "is_active")
    search_fields = ("code", "name_es", "name_en")
    ordering_fields = ("code", "credits")


@extend_schema_view(
    list=extend_schema(summary="List groups"),
    create=extend_schema(summary="Open a group"),
)
class StudentGroupViewSet(SoftDeleteModelViewSet):
    """Sections of a programme -- the unit a timetable and a register need."""

    queryset = (
        StudentGroup.objects.select_related("program", "academic_year", "tutor")
        .annotate(
            # Answered here rather than by the client counting enrolments, because
            # the list is the screen where somebody decides which group is full.
            student_count=Count(
                "enrollments",
                filter=Q(
                    enrollments__deleted_at__isnull=True,
                    enrollments__status__in=(EnrollmentStatus.ACTIVE, EnrollmentStatus.PENDING),
                ),
                distinct=True,
            )
            # Repeated from the model's Meta on purpose: counting groups by their
            # students adds a GROUP BY, and Django then reports the queryset as
            # unordered however the model is declared -- which paginates a school's
            # groups in whatever order Postgres feels like returning them.
        )
        .order_by("academic_year__start_date", "program__code", "name")
    )
    serializer_class = StudentGroupSerializer
    permission_classes = (ModulePermission,)
    module = Module.ACADEMIC
    filterset_fields = ("program", "academic_year", "tutor", "is_active")
    search_fields = ("name", "room")
    ordering_fields = ("name",)


class EnrollmentViewSet(SoftDeleteModelViewSet):
    queryset = Enrollment.objects.select_related("student", "program", "academic_year", "group")
    serializer_class = EnrollmentSerializer
    permission_classes = (ModulePermission,)
    module = Module.ACADEMIC
    filterset_fields = ("status", "program", "academic_year", "student", "group", "is_active")
    search_fields = ("student__first_name", "student__last_name", "student__email")
    ordering_fields = ("enrolled_on", "status")


@extend_schema_view(
    list=extend_schema(summary="List evaluation periods"),
    create=extend_schema(summary="Open an evaluation period"),
)
class TermViewSet(SoftDeleteModelViewSet):
    queryset = Term.objects.select_related("academic_year")
    serializer_class = TermSerializer
    permission_classes = (ModulePermission,)
    module = Module.GRADES
    filterset_fields = ("academic_year", "is_current", "is_active")
    ordering_fields = ("ordinal", "start_date")


@extend_schema_view(
    list=extend_schema(summary="List assessments"),
    create=extend_schema(summary="Add an assessment to a subject"),
)
class AssessmentViewSet(SoftDeleteModelViewSet):
    queryset = Assessment.objects.select_related("subject", "term")
    serializer_class = AssessmentSerializer
    permission_classes = (ModulePermission, TeachesThisSubject)
    module = Module.GRADES
    filterset_fields = ("subject", "term", "is_active")
    ordering_fields = ("due_date", "name")

    def perform_create(self, serializer: Any) -> None:
        """A teacher may only add assessments to their own subjects.

        ``TeachesThisSubject`` is object-level and there is no object yet on
        create, so the same rule is applied to the subject being written to.
        """
        subject = serializer.validated_data["subject"]
        if not may_grade_subject(self.request.user, subject):
            raise PermissionDenied(TeachesThisSubject.message)
        serializer.save()


class GradebookView(APIView):
    """One subject, one period: every enrolled student and every mark.

    A single request rather than a grid the client assembles from three, because
    the interface is useless until it has all of it -- and because the average
    is computed the same way for everyone, server-side, instead of being
    reimplemented in the browser.
    """

    permission_classes = (ModulePermission,)
    module = Module.GRADES
    serializer_class = GradebookSerializer

    @extend_schema(
        summary="The gradebook for a subject in a period",
        parameters=[
            OpenApiParameter("subject", str, required=True),
            OpenApiParameter("term", str, required=True),
        ],
        responses={200: GradebookSerializer},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        subject = get_object_or_404(Subject, pk=request.query_params.get("subject"))
        term = get_object_or_404(Term, pk=request.query_params.get("term"))

        assessments, rows = gradebook.build(subject, term)

        return Response(
            {
                "subject": str(subject.id),
                "term": str(term.id),
                "assessments": AssessmentSerializer(assessments, many=True).data,
                # So the interface can say "8.63 / 10" rather than leaving the
                # reader to guess what the number is out of.
                "average_scale": gradebook.average_scale(assessments),
                "rows": [
                    {
                        "enrollment_id": str(row.enrollment_id),
                        "student_id": str(row.student_id),
                        "student_name": row.student_name,
                        "scores": {str(key): value for key, value in row.scores.items()},
                        "average": row.average,
                        "graded_count": row.graded_count,
                    }
                    for row in rows
                ],
                # So the interface renders inputs or plain text, instead of
                # offering edits the API will refuse.
                "can_edit": may_grade_subject(request.user, subject),
            }
        )


class AssessmentGradesView(APIView):
    """Record every mark for one assessment in a single call.

    Marking is done a column at a time -- a teacher sits with one exam and goes
    down the list -- so the endpoint matches the act. One request per cell would
    also make a half-saved column the normal outcome of a dropped connection;
    this way the column lands or it does not.
    """

    permission_classes = (ModulePermission,)
    module = Module.GRADES
    serializer_class = GradeInputSerializer

    @extend_schema(
        summary="Record marks for an assessment",
        request=GradeInputSerializer(many=True),
        responses={200: GradeSerializer(many=True)},
    )
    def put(self, request: Request, assessment_id: str, *args: Any, **kwargs: Any) -> Response:
        assessment = get_object_or_404(
            Assessment.objects.select_related("subject"), pk=assessment_id
        )
        if not may_grade_subject(request.user, assessment.subject):
            raise PermissionDenied(TeachesThisSubject.message)

        serializer = GradeInputSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        grades = gradebook.record(
            assessment=assessment,
            entries=serializer.validated_data,
            recorded_by=request.user,
        )
        return Response(GradeSerializer(grades, many=True).data)


class TimetableSlotFilter(django_filters.FilterSet):
    """``?teacher=`` is the question a teacher asks; the rest is plumbing."""

    teacher = django_filters.UUIDFilter(field_name="subject__teacher")

    class Meta:
        model = TimetableSlot
        fields = ("group", "subject", "weekday", "teacher", "is_active")


@extend_schema_view(
    list=extend_schema(summary="List timetable entries"),
    create=extend_schema(
        summary="Add a class to the timetable",
        description=(
            "Refused when the group, the teacher or the room is already busy at "
            "that hour. Every clash is reported at once, on the field that "
            "caused it."
        ),
    ),
)
class TimetableSlotViewSet(SoftDeleteModelViewSet):
    queryset = TimetableSlot.objects.select_related(
        "group", "group__program", "subject", "subject__teacher"
    )
    serializer_class = TimetableSlotSerializer
    permission_classes = (ModulePermission,)
    module = Module.SCHEDULE
    filterset_class = TimetableSlotFilter
    ordering_fields = ("weekday", "start_time")


class TodayClassesView(APIView):
    """The classes on one date, with whether the roll has been taken.

    The entry point to attendance: a teacher opens the day and sees what they
    are teaching and what is still unrecorded. Two questions in one call,
    because the second one -- "have I done this yet" -- is the whole reason for
    the screen, and asking it per class would be one request per row.
    """

    permission_classes = (ModulePermission,)
    module = Module.ATTENDANCE
    serializer_class = TimetableSlotSerializer

    @extend_schema(
        summary="Classes on a date, and their registers",
        parameters=[
            OpenApiParameter("date", str, description="Defaults to today."),
            OpenApiParameter("group", str, required=False),
            OpenApiParameter("teacher", str, required=False),
        ],
        responses={200: RollSerializer(many=True)},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from . import timetable

        on = _requested_date(request)
        group = request.query_params.get("group") or None
        teacher = request.query_params.get("teacher") or None

        slots = list(timetable.slots_on(on, teacher=teacher, group=group))
        sessions = timetable.sessions_by_slot(on, slots)

        return Response(
            [
                {
                    "slot": TimetableSlotSerializer(slot).data,
                    "date": on,
                    "session": (
                        ClassSessionSerializer(sessions[slot.id]).data
                        if slot.id in sessions
                        else None
                    ),
                    # The list is a summary; the marks come from the register
                    # itself, which is one more click away.
                    "rows": [],
                    "can_edit": may_take_roll(request.user, slot),
                }
                for slot in slots
            ]
        )


class RollView(APIView):
    """Read and write the register for one class on one date."""

    permission_classes = (ModulePermission,)
    module = Module.ATTENDANCE
    serializer_class = RollSerializer

    @extend_schema(
        summary="The register for a class on a date",
        parameters=[
            OpenApiParameter("slot", str, required=True),
            OpenApiParameter("date", str, description="Defaults to today."),
        ],
        responses={200: RollSerializer},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        slot = get_object_or_404(
            TimetableSlot.objects.select_related("group", "subject", "subject__teacher"),
            pk=request.query_params.get("slot"),
        )
        on = _requested_date(request)
        _check_weekday(slot, on)

        session, rows = attendance.build(slot, on)
        return Response(self._payload(request, slot, on, session, rows))

    @extend_schema(
        summary="Take the roll",
        request=RollInputSerializer,
        responses={200: RollSerializer},
    )
    def put(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        payload = RollInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        slot = get_object_or_404(
            TimetableSlot.objects.select_related("group", "subject", "subject__teacher"),
            pk=data["slot"],
        )
        if not may_take_roll(request.user, slot):
            raise PermissionDenied(_("You can only take the roll for classes you teach."))

        on = data["date"]
        _check_weekday(slot, on)

        attendance.record(
            slot=slot,
            on=on,
            entries=data["entries"],
            taken_by=request.user,
            session_status=data["status"],
            note=data.get("note", ""),
        )

        session, rows = attendance.build(slot, on)
        return Response(self._payload(request, slot, on, session, rows))

    @staticmethod
    def _payload(
        request: Request, slot: TimetableSlot, on: date_type, session: Any, rows: list
    ) -> dict:
        return {
            "slot": TimetableSlotSerializer(slot).data,
            "date": on,
            "session": ClassSessionSerializer(session).data if session else None,
            "rows": [
                {
                    "enrollment_id": str(row.enrollment_id),
                    "student_id": str(row.student_id),
                    "student_name": row.student_name,
                    "status": row.status,
                    "note": row.note,
                }
                for row in rows
            ],
            "can_edit": may_take_roll(request.user, slot),
        }


class AttendanceTrendView(APIView):
    """Attendance rate per day, for the dashboard."""

    permission_classes = (ModulePermission,)
    module = Module.ATTENDANCE
    serializer_class = AttendancePointSerializer

    @extend_schema(
        summary="Daily attendance rate",
        description=(
            "A trailing window ending today. ``recorded`` is how many marks the "
            "percentage rests on: a day with none is a day nobody took a roll, "
            "not a day of zero attendance."
        ),
        parameters=[OpenApiParameter("days", int, description="Default 7, max 90.")],
        responses={200: AttendancePointSerializer(many=True)},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        try:
            days = int(request.query_params.get("days", 7))
        except ValueError:
            days = 7
        days = max(1, min(days, 90))

        return Response(
            AttendancePointSerializer(attendance.daily_rates(days=days), many=True).data
        )


def _requested_date(request: Request) -> date_type:
    raw = request.query_params.get("date")
    if not raw:
        return timezone.localdate()
    parsed = date_type.fromisoformat(raw) if _is_iso_date(raw) else None
    if parsed is None:
        raise ValidationError({"date": _("Use the format YYYY-MM-DD.")})
    return parsed


def _is_iso_date(raw: str) -> bool:
    try:
        date_type.fromisoformat(raw)
    except ValueError:
        return False
    return True


def _check_weekday(slot: TimetableSlot, on: date_type) -> None:
    """A Monday class has no register on a Wednesday.

    Without this, a mistyped date silently opens a session for a lesson that
    never takes place on that day, and the absences it records are against a
    class nobody was expected at.
    """
    if slot.weekday != on.isoweekday():
        raise ValidationError(
            {"date": _("That class does not meet on %(day)s.") % {"day": on.isoformat()}}
        )
