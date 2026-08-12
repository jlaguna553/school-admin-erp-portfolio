from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from .models import AcademicYear, Enrollment, Program, Subject


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_current", "is_active")
    list_filter = ("is_current", "is_active")


@admin.register(Program)
class ProgramAdmin(TranslationAdmin):
    """``TranslationAdmin`` renders one input per language for translated fields."""

    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name_es", "name_en")


@admin.register(Subject)
class SubjectAdmin(TranslationAdmin):
    list_display = ("code", "name", "program", "credits", "teacher", "is_active")
    list_filter = ("program", "is_active")
    search_fields = ("code", "name_es", "name_en")
    autocomplete_fields = ("teacher",)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "program", "academic_year", "status", "enrolled_on")
    list_filter = ("status", "program", "academic_year")
    search_fields = ("student__email", "student__first_name", "student__last_name")
