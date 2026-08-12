from decimal import Decimal
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.tenants.models import Currency

from .models import Invoice, InvoiceLine, Payment, PaymentMethod


class InvoiceLineSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = InvoiceLine
        fields = (
            "id",
            "concept_id",
            "description",
            "quantity",
            "unit_price",
            "line_total",
        )
        read_only_fields = ("id", "line_total")


class InvoiceLineInputSerializer(serializers.Serializer):
    concept_id = serializers.UUIDField(required=False, allow_null=True)
    description = serializers.CharField(max_length=300)
    quantity = serializers.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.00"))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)


class PaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(
        source="recorded_by.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "invoice",
            "amount",
            "method",
            "reference",
            "received_on",
            "recorded_by",
            "recorded_by_name",
            "created_at",
        )
        read_only_fields = ("id", "invoice", "recorded_by", "created_at")


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = (
            "id",
            "number",
            "enrollment_id",
            "student_id",
            "program_id",
            "student_name_snapshot",
            "program_name_snapshot",
            "status",
            "currency",
            "issue_date",
            "due_date",
            "notes",
            "subtotal",
            "amount_paid",
            "balance",
            "lines",
            "payments",
            "is_active",
            "created_at",
        )
        read_only_fields = fields  # Invoices are created through the service layer.


class InvoiceCreateSerializer(serializers.Serializer):
    """Input for ``POST /api/v1/billing/invoices/``.

    ``enrollment_id`` is a bare UUID rather than a related field: billing has no
    ForeignKey into the academic context (rule A.2), so DRF cannot and must not
    validate it against a queryset. The service layer validates it instead.
    """

    enrollment_id = serializers.UUIDField(
        help_text=_("UUID of an enrollment in the academic context.")
    )
    lines = InvoiceLineInputSerializer(many=True)
    issue_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False)
    # Omitted on purpose: the institution's configured currency is used. Sent
    # explicitly it is still validated against the supported list.
    currency = serializers.ChoiceField(
        choices=Currency.choices, required=False, allow_null=True, default=None
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_lines(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not value:
            raise serializers.ValidationError(_("An invoice needs at least one line."))
        return value


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    method = serializers.ChoiceField(choices=PaymentMethod.choices, default=PaymentMethod.TRANSFER)
    reference = serializers.CharField(required=False, allow_blank=True, default="", max_length=120)
    received_on = serializers.DateField(required=False)

    def validate_amount(self, value: Decimal) -> Decimal:
        if value <= Decimal("0.00"):
            raise serializers.ValidationError(_("The payment amount must be positive."))
        return value
