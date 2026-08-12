from decimal import Decimal
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from . import timetable
from .models import (
    AcademicYear,
    Assessment,
    Attendance,
    AttendanceStatus,
    ClassSession,
    Enrollment,
    Grade,
    Program,
    SessionStatus,
    StudentGroup,
    Subject,
    Term,
    TimetableSlot,
)


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = (
            "id",
            "name",
            "start_date",
            "end_date",
            "is_current",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "is_active", "created_at")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end = attrs.get("end_date") or getattr(self.instance, "end_date", None)
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": _("The end date must be after the start date.")}
            )
        return attrs


class ProgramSerializer(serializers.ModelSerializer):
    """``name``/``description`` resolve to the request's active language.

    modeltranslation swaps in the column for the active locale, so clients get
    ``name`` already localised and never see ``name_es`` / ``name_en``.
    """

    class Meta:
        model = Program
        fields = (
            "id",
            "code",
            "name",
            "description",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "is_active", "created_at")


class ProgramTranslationsSerializer(serializers.ModelSerializer):
    """Admin-facing variant exposing every language column explicitly."""

    # modeltranslation generates the per-language columns by copying the
    # original field, and DRF then infers them as required/non-blank. Left
    # alone, a programme could not be saved without filling in *every*
    # language. Spanish is the project's default and stays mandatory; English
    # is optional and falls back to Spanish on read.
    name_es = serializers.CharField(required=True, allow_blank=False, max_length=200)
    name_en = serializers.CharField(required=False, allow_blank=True, max_length=200)
    description_es = serializers.CharField(required=False, allow_blank=True)
    description_en = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Program
        fields = (
            "id",
            "code",
            "name_es",
            "name_en",
            "description_es",
            "description_en",
        )
        read_only_fields = ("id",)


class SubjectSerializer(serializers.ModelSerializer):
    program_code = serializers.CharField(source="program.code", read_only=True)
    teacher_name = serializers.CharField(
        source="teacher.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Subject
        fields = (
            "id",
            "code",
            "name",
            "description",
            "credits",
            "program",
            "program_code",
            "teacher",
            "teacher_name",
            "is_active",
        )
        read_only_fields = ("id", "is_active")


class StudentGroupSerializer(serializers.ModelSerializer):
    program_code = serializers.CharField(source="program.code", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    tutor_name = serializers.CharField(source="tutor.get_full_name", read_only=True, default=None)
    student_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = StudentGroup
        fields = (
            "id",
            "name",
            "program",
            "program_code",
            "academic_year",
            "academic_year_name",
            "tutor",
            "tutor_name",
            "room",
            "student_count",
            "is_active",
        )
        read_only_fields = ("id", "is_active")


class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    program_name = serializers.CharField(source="program.name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True, default=None)

    class Meta:
        model = Enrollment
        fields = (
            "id",
            "student",
            "student_name",
            "program",
            "program_name",
            "academic_year",
            "academic_year_name",
            "group",
            "group_name",
            "status",
            "enrolled_on",
            "is_active",
        )
        read_only_fields = ("id", "is_active")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """A group belongs to one programme and one year; so must its members.

        Without this an enrolment could sit in a group from another programme
        entirely, and the register for that group would list a student nobody
        in the room has ever taught.
        """
        group = attrs.get("group", getattr(self.instance, "group", None))
        if group is None:
            return attrs

        program = attrs.get("program", getattr(self.instance, "program", None))
        year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))

        if program is not None and group.program_id != program.pk:
            raise serializers.ValidationError(
                {"group": _("That group belongs to a different programme.")}
            )
        if year is not None and group.academic_year_id != year.pk:
            raise serializers.ValidationError(
                {"group": _("That group belongs to a different academic year.")}
            )
        return attrs


class TermSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)

    class Meta:
        model = Term
        fields = (
            "id",
            "academic_year",
            "academic_year_name",
            "name",
            "ordinal",
            "start_date",
            "end_date",
            "is_current",
            "is_active",
        )
        read_only_fields = ("id", "is_active")
        # DRF derives a UniqueTogetherValidator from the model constraint and
        # runs it before `validate`, so its message -- "academic_year, ordinal
        # must form a unique set", filed under non_field_errors -- would always
        # win. The check below says the same thing on the field somebody can
        # actually change. The database constraint is still the real guarantee.
        validators = ()  # noqa: RUF012

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"end_date": _("The end date cannot precede the start date.")}
            )

        # The uniqueness constraint reports itself as "academic_year, ordinal
        # must form a unique set", under `non_field_errors`. True, and no help
        # to whoever has to change something: the message belongs on the field
        # they can act on.
        year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        ordinal = attrs.get("ordinal", getattr(self.instance, "ordinal", None))
        if year is not None and ordinal is not None:
            clash = Term.objects.filter(academic_year=year, ordinal=ordinal)
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError(
                    {"ordinal": _("This year already has a period in that position.")}
                )

        return attrs


class AssessmentSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)

    class Meta:
        model = Assessment
        fields = (
            "id",
            "subject",
            "subject_name",
            "term",
            "term_name",
            "name",
            "max_score",
            "weight",
            "due_date",
            "is_active",
        )
        read_only_fields = ("id", "is_active")


class GradeInputSerializer(serializers.Serializer):
    """One cell of the gradebook, as the bulk endpoint receives it."""

    enrollment_id = serializers.UUIDField()
    # Null clears a mark. Distinct from zero, which is a mark of zero -- the two
    # must not collapse into each other.
    score = serializers.DecimalField(
        max_digits=6, decimal_places=2, allow_null=True, min_value=Decimal("0")
    )
    comment = serializers.CharField(required=False, allow_blank=True, max_length=300)


class GradeSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="enrollment.student.get_full_name", read_only=True)
    recorded_by_name = serializers.CharField(
        source="recorded_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Grade
        fields = (
            "id",
            "assessment",
            "enrollment",
            "student_name",
            "score",
            "comment",
            "recorded_by",
            "recorded_by_name",
            "updated_at",
        )
        read_only_fields = fields


class GradebookRowSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField(read_only=True)
    student_id = serializers.UUIDField(read_only=True)
    student_name = serializers.CharField(read_only=True)
    # Declares its value type so the generated client types are usable: a bare
    # DictField becomes `{}` on the other side, which is no type at all.
    scores = serializers.DictField(
        child=serializers.DecimalField(max_digits=6, decimal_places=2), read_only=True
    )
    average = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    graded_count = serializers.IntegerField(read_only=True)


class GradebookSerializer(serializers.Serializer):
    """The whole grid: the assessments across the top, the students down."""

    subject = serializers.UUIDField(read_only=True)
    term = serializers.UUIDField(read_only=True)
    assessments = AssessmentSerializer(many=True, read_only=True)
    average_scale = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    rows = GradebookRowSerializer(many=True, read_only=True)
    can_edit = serializers.BooleanField(read_only=True)


class TimetableSlotSerializer(serializers.ModelSerializer):
    # The group's own name is just "A"; on a timetable it has to say which
    # programme's A it is.
    group_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    teacher_name = serializers.CharField(
        source="subject.teacher.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = TimetableSlot
        fields = (
            "id",
            "group",
            "group_name",
            "subject",
            "subject_name",
            "subject_code",
            "teacher_name",
            "weekday",
            "start_time",
            "end_time",
            "room",
            "is_active",
        )
        read_only_fields = ("id", "is_active")

    def get_group_name(self, obj: TimetableSlot) -> str:
        return str(obj.group)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        def field(name: str) -> Any:
            return attrs.get(name, getattr(self.instance, name, None))

        start, end = field("start_time"), field("end_time")
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_time": _("The class must end after it starts.")}
            )

        group, subject = field("group"), field("subject")
        weekday, room = field("weekday"), field("room") or ""

        if group is not None and subject.program_id != group.program_id:
            raise serializers.ValidationError(
                {"subject": _("That subject is not taught in this group's programme.")}
            )

        clashes = timetable.find_clashes(
            group=group,
            subject=subject,
            weekday=weekday,
            start=start,
            end=end,
            room=room,
            exclude_pk=self.instance.pk if self.instance else None,
        )
        if clashes:
            # Filed under the field that caused each clash, so the form marks
            # the thing to change rather than shouting at the whole dialog.
            field_for = {"group": "group", "teacher": "subject", "room": "room"}
            errors: dict[str, list[Any]] = {}
            for clash in clashes:
                errors.setdefault(field_for[clash.resource], []).append(clash.message)
            raise serializers.ValidationError(errors)

        return attrs


class ClassSessionSerializer(serializers.ModelSerializer):
    taken_by_name = serializers.CharField(
        source="taken_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = ClassSession
        fields = ("id", "slot", "date", "status", "note", "taken_by", "taken_by_name", "taken_at")
        read_only_fields = fields


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="enrollment.student.get_full_name", read_only=True)

    class Meta:
        model = Attendance
        fields = ("id", "session", "enrollment", "student_name", "status", "note", "updated_at")
        read_only_fields = fields


class RollEntrySerializer(serializers.Serializer):
    """One student's mark, as the register is submitted."""

    enrollment_id = serializers.UUIDField()
    # Null erases the mark, leaving the student unrecorded. Not the same as
    # marking them present, and not the same as marking them absent.
    status = serializers.ChoiceField(choices=AttendanceStatus.choices, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=300)


class RollRowSerializer(serializers.Serializer):
    enrollment_id = serializers.UUIDField(read_only=True)
    student_id = serializers.UUIDField(read_only=True)
    student_name = serializers.CharField(read_only=True)
    # Nullable, and the generated client has to know it: an unmarked student is
    # the ordinary state of a register nobody has taken yet.
    status = serializers.ChoiceField(
        choices=AttendanceStatus.choices, read_only=True, allow_null=True
    )
    note = serializers.CharField(read_only=True)


class RollSerializer(serializers.Serializer):
    """A register: the class, the date, and everyone who should be in the room."""

    slot = TimetableSlotSerializer(read_only=True)
    date = serializers.DateField(read_only=True)
    session = ClassSessionSerializer(read_only=True, allow_null=True)
    rows = RollRowSerializer(many=True, read_only=True)
    can_edit = serializers.BooleanField(read_only=True)


class RollInputSerializer(serializers.Serializer):
    """Taking the roll: the whole room in one call."""

    slot = serializers.UUIDField()
    date = serializers.DateField()
    status = serializers.ChoiceField(choices=SessionStatus.choices, default=SessionStatus.HELD)
    note = serializers.CharField(required=False, allow_blank=True, max_length=300)
    entries = RollEntrySerializer(many=True, required=False, default=list)


class AttendancePointSerializer(serializers.Serializer):
    """One day of the attendance trend."""

    date = serializers.DateField(read_only=True)
    value = serializers.FloatField(read_only=True)
    # How many marks the percentage rests on. A day with none is not zero per
    # cent attendance -- it is a day nobody took a roll, and the client needs to
    # be able to tell the difference without guessing from the value.
    recorded = serializers.IntegerField(read_only=True)
