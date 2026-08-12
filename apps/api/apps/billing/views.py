from typing import Any

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.modules import Module
from apps.core.permissions import ModulePermission
from apps.core.viewsets import SoftDeleteModelViewSet

from . import services
from .models import Invoice
from .serializers import (
    InvoiceCreateSerializer,
    InvoiceSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
)


@extend_schema_view(
    create=extend_schema(
        summary="Issue an invoice",
        request=InvoiceCreateSerializer,
        responses={201: InvoiceSerializer},
        description=(
            "Validates the enrollment through the academic context's service "
            "layer, then issues the invoice with a snapshot of the student and "
            "programme names."
        ),
    ),
    destroy=extend_schema(summary="Void an invoice (soft delete)"),
)
class InvoiceViewSet(SoftDeleteModelViewSet):
    queryset = Invoice.objects.prefetch_related("lines", "payments")
    permission_classes = (ModulePermission,)
    module = Module.BILLING
    filterset_fields = ("status", "currency", "student_id", "enrollment_id")
    search_fields = ("number", "student_name_snapshot")
    ordering_fields = ("issue_date", "due_date", "number")

    def get_serializer_class(self) -> type[Any]:
        if self.action == "create":
            return InvoiceCreateSerializer
        if self.action == "register_payment":
            return PaymentCreateSerializer
        return InvoiceSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        invoice = services.create_invoice_for_enrollment(
            enrollment_id=data["enrollment_id"],
            lines=data["lines"],
            issue_date=data.get("issue_date"),
            due_date=data.get("due_date"),
            currency=data["currency"],
            issued_by_id=request.user.id,
            notes=data.get("notes", ""),
        )
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Record a payment",
        request=PaymentCreateSerializer,
        responses={201: PaymentSerializer},
    )
    @action(detail=True, methods=["post"], url_path="payments")
    def register_payment(self, request: Request, pk: str | None = None) -> Response:
        invoice = self.get_object()
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payment = services.register_payment(
            invoice=invoice,
            amount=data["amount"],
            method=data["method"],
            received_on=data.get("received_on"),
            reference=data.get("reference", ""),
            recorded_by_id=request.user.id,
        )
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Enrollment context for this invoice",
        description=(
            "Resolves the live academic state behind the invoice's stored "
            "``enrollment_id`` via the academic service layer -- no JOIN."
        ),
    )
    @action(detail=True, methods=["get"], url_path="enrollment")
    def enrollment(self, request: Request, pk: str | None = None) -> Response:
        from apps.academic import services as academic_services

        invoice = self.get_object()
        snapshot = academic_services.get_enrollment_snapshot(invoice.enrollment_id)
        if snapshot is None:
            return Response({"detail": None}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "enrollment_id": str(snapshot.enrollment_id),
                "student_id": str(snapshot.student_id),
                "student_full_name": snapshot.student_full_name,
                "program_code": snapshot.program_code,
                "program_name": snapshot.program_name,
                "academic_year_name": snapshot.academic_year_name,
                "status": snapshot.status,
                "is_billable": snapshot.is_billable,
            }
        )
