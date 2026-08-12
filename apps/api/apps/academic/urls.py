from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AcademicYearViewSet,
    AssessmentGradesView,
    AssessmentViewSet,
    AttendanceTrendView,
    EnrollmentViewSet,
    GradebookView,
    ProgramViewSet,
    RollView,
    StudentGroupViewSet,
    SubjectViewSet,
    TermViewSet,
    TimetableSlotViewSet,
    TodayClassesView,
)

app_name = "academic"

router = DefaultRouter()
router.register("academic-years", AcademicYearViewSet, basename="academic-year")
router.register("programs", ProgramViewSet, basename="program")
router.register("subjects", SubjectViewSet, basename="subject")
router.register("groups", StudentGroupViewSet, basename="group")
router.register("enrollments", EnrollmentViewSet, basename="enrollment")
router.register("terms", TermViewSet, basename="term")
router.register("assessments", AssessmentViewSet, basename="assessment")
router.register("timetable", TimetableSlotViewSet, basename="timetable-slot")

urlpatterns = [
    # Read the whole grid in one call, and write a column in one call: both
    # match how marking is actually done, and neither fits a router.
    path("gradebook/", GradebookView.as_view(), name="gradebook"),
    path(
        "assessments/<uuid:assessment_id>/grades/",
        AssessmentGradesView.as_view(),
        name="assessment-grades",
    ),
    # The register is read and written whole, for one class on one date, so it
    # is one address rather than a collection of marks.
    path("roll/", RollView.as_view(), name="roll"),
    path("classes/today/", TodayClassesView.as_view(), name="classes-today"),
    path("attendance/weekly/", AttendanceTrendView.as_view(), name="attendance-weekly"),
    *router.urls,
]
