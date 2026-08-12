from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AcademicConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.academic"
    label = "academic"
    verbose_name = _("Academic")
