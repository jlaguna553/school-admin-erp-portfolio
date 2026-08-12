from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("last_name", "first_name")
    list_display = ("email", "first_name", "last_name", "role", "language", "is_active")
    list_filter = ("role", "is_active", "is_staff", "language")
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = ("last_login", "date_joined", "created_at", "updated_at", "deleted_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone")}),
        (_("Role & locale"), {"fields": ("role", "language")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined", "deleted_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "role",
                    "language",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
