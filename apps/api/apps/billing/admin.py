from django.contrib import admin

from .models import Invoice, InvoiceLine, Payment


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    readonly_fields = ("line_total",)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "student_name_snapshot",
        "status",
        "currency",
        "issue_date",
        "due_date",
    )
    list_filter = ("status", "currency", "issue_date")
    search_fields = ("number", "student_name_snapshot")
    # enrollment_id/student_id are cross-context UUIDs, so there is no
    # autocomplete widget to offer -- they are intentionally raw.
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    inlines = (InvoiceLineInline, PaymentInline)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "method", "received_on", "recorded_by")
    list_filter = ("method", "received_on")
    search_fields = ("reference", "invoice__number")
