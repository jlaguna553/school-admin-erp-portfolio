from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import Client, Domain


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1


@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("name", "schema_name", "default_language", "is_active", "paid_until")
    list_filter = ("is_active", "on_trial", "default_language")
    search_fields = ("name", "legal_name", "schema_name")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    inlines = (DomainInline,)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("domain",)
