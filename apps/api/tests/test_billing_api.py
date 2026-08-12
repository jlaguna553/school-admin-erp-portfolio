"""
Billing API and the academic/billing boundary.

Because billing holds no ForeignKey into academic (rule A.2), the database
cannot enforce that `enrollment_id` points at anything real. The service layer
is what keeps the reference honest — so these tests treat that validation as a
correctness requirement rather than a nicety.
"""

from decimal import Decimal

import pytest
from django_tenants.utils import schema_context

from conftest import TENANT_A

pytestmark = pytest.mark.django_db


def _invoice_payload(enrollment_id, **overrides):
    payload = {
        "enrollment_id": str(enrollment_id),
        # No currency: the institution's own is used. See tests/test_currency.py.
        "lines": [
            {"description": "Matrícula anual", "unit_price": "450.00", "quantity": "1"},
            {"description": "Material escolar", "unit_price": "75.50", "quantity": "1"},
        ],
    }
    payload.update(overrides)
    return payload


class TestInvoiceCreation:
    def test_accountant_can_issue_an_invoice(self, as_accountant_a, enrollment_a):
        response = as_accountant_a.post(
            "/api/v1/billing/invoices/", _invoice_payload(enrollment_a.id), format="json"
        )
        assert response.status_code == 201, response.data

        data = response.data
        assert data["status"] == "issued"
        assert Decimal(data["subtotal"]) == Decimal("525.50")
        assert Decimal(data["balance"]) == Decimal("525.50")
        assert data["number"].startswith("INV-")

    def test_labels_are_snapshotted_at_issue_time(self, as_accountant_a, enrollment_a):
        """A financial document must not mutate when the enrollment changes."""
        response = as_accountant_a.post(
            "/api/v1/billing/invoices/", _invoice_payload(enrollment_a.id), format="json"
        )
        invoice_id = response.data["id"]
        original_name = response.data["student_name_snapshot"]

        with schema_context(TENANT_A["schema"]):
            student = enrollment_a.student
            student.last_name = "Renamed"
            student.save(update_fields=["last_name", "updated_at"])

        fetched = as_accountant_a.get(f"/api/v1/billing/invoices/{invoice_id}/")
        assert fetched.data["student_name_snapshot"] == original_name
        assert "Renamed" not in fetched.data["student_name_snapshot"]

    def test_unknown_enrollment_is_rejected(self, as_accountant_a):
        """Nothing in the schema enforces this — the service must."""
        import uuid

        response = as_accountant_a.post(
            "/api/v1/billing/invoices/", _invoice_payload(uuid.uuid4()), format="json"
        )
        assert response.status_code == 422
        assert response.data["error"]["code"] == "business_rule_violation"

    def test_withdrawn_enrollment_is_not_billable(self, as_accountant_a, enrollment_a):
        from apps.academic.models import EnrollmentStatus

        with schema_context(TENANT_A["schema"]):
            enrollment_a.status = EnrollmentStatus.WITHDRAWN
            enrollment_a.save(update_fields=["status", "updated_at"])

        response = as_accountant_a.post(
            "/api/v1/billing/invoices/", _invoice_payload(enrollment_a.id), format="json"
        )
        assert response.status_code == 422

    def test_invoice_needs_at_least_one_line(self, as_accountant_a, enrollment_a):
        response = as_accountant_a.post(
            "/api/v1/billing/invoices/",
            _invoice_payload(enrollment_a.id, lines=[]),
            format="json",
        )
        assert response.status_code == 400
        assert "lines" in response.data["error"]["details"]

    def test_numbers_are_sequential(self, as_accountant_a, enrollment_a):
        first = as_accountant_a.post(
            "/api/v1/billing/invoices/", _invoice_payload(enrollment_a.id), format="json"
        )
        second = as_accountant_a.post(
            "/api/v1/billing/invoices/", _invoice_payload(enrollment_a.id), format="json"
        )
        assert first.data["number"] != second.data["number"]
        assert int(second.data["number"].rsplit("-", 1)[1]) == (
            int(first.data["number"].rsplit("-", 1)[1]) + 1
        )


class TestPermissions:
    def test_teacher_cannot_reach_billing(self, as_teacher_a, enrollment_a):
        assert as_teacher_a.get("/api/v1/billing/invoices/").status_code == 403

    def test_student_cannot_reach_billing(self, as_student_a):
        assert as_student_a.get("/api/v1/billing/invoices/").status_code == 403

    def test_admin_can_reach_billing(self, as_admin_a):
        assert as_admin_a.get("/api/v1/billing/invoices/").status_code == 200


class TestPayments:
    @pytest.fixture
    def invoice(self, as_accountant_a, enrollment_a):
        response = as_accountant_a.post(
            "/api/v1/billing/invoices/", _invoice_payload(enrollment_a.id), format="json"
        )
        assert response.status_code == 201
        return response.data

    def test_partial_payment_moves_status(self, as_accountant_a, invoice):
        response = as_accountant_a.post(
            f"/api/v1/billing/invoices/{invoice['id']}/payments/",
            {"amount": "100.00", "method": "transfer"},
            format="json",
        )
        assert response.status_code == 201, response.data

        refreshed = as_accountant_a.get(f"/api/v1/billing/invoices/{invoice['id']}/")
        assert refreshed.data["status"] == "partially_paid"
        assert Decimal(refreshed.data["balance"]) == Decimal("425.50")

    def test_full_payment_marks_paid(self, as_accountant_a, invoice):
        as_accountant_a.post(
            f"/api/v1/billing/invoices/{invoice['id']}/payments/",
            {"amount": invoice["subtotal"], "method": "card"},
            format="json",
        )
        refreshed = as_accountant_a.get(f"/api/v1/billing/invoices/{invoice['id']}/")
        assert refreshed.data["status"] == "paid"
        assert Decimal(refreshed.data["balance"]) == Decimal("0.00")

    def test_overpayment_is_rejected(self, as_accountant_a, invoice):
        response = as_accountant_a.post(
            f"/api/v1/billing/invoices/{invoice['id']}/payments/",
            {"amount": "10000.00", "method": "cash"},
            format="json",
        )
        assert response.status_code == 422
        assert response.data["error"]["code"] == "business_rule_violation"

    def test_negative_payment_is_rejected(self, as_accountant_a, invoice):
        response = as_accountant_a.post(
            f"/api/v1/billing/invoices/{invoice['id']}/payments/",
            {"amount": "-50.00", "method": "cash"},
            format="json",
        )
        assert response.status_code == 400

    def test_error_message_is_localised(self, as_accountant_a, invoice):
        spanish = as_accountant_a.post(
            f"/api/v1/billing/invoices/{invoice['id']}/payments/",
            {"amount": "10000.00", "method": "cash"},
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        english = as_accountant_a.post(
            f"/api/v1/billing/invoices/{invoice['id']}/payments/",
            {"amount": "10000.00", "method": "cash"},
            format="json",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        assert "excede" in spanish.data["error"]["message"]
        assert "exceeds" in english.data["error"]["message"]


class TestCrossContextResolution:
    def test_enrollment_endpoint_resolves_without_a_join(self, as_accountant_a, enrollment_a):
        """Billing reads academic state through the service layer, not the ORM."""
        created = as_accountant_a.post(
            "/api/v1/billing/invoices/", _invoice_payload(enrollment_a.id), format="json"
        )
        response = as_accountant_a.get(f"/api/v1/billing/invoices/{created.data['id']}/enrollment/")
        assert response.status_code == 200
        assert response.data["program_code"] == "PRI"
        assert response.data["status"] == "active"
        assert response.data["is_billable"] is True

    def test_invoice_survives_a_deleted_enrollment(self, as_accountant_a, enrollment_a):
        """With no FK there is no cascade: the financial record must remain."""
        created = as_accountant_a.post(
            "/api/v1/billing/invoices/", _invoice_payload(enrollment_a.id), format="json"
        )
        invoice_id = created.data["id"]

        with schema_context(TENANT_A["schema"]):
            enrollment_a.delete()  # soft delete

        fetched = as_accountant_a.get(f"/api/v1/billing/invoices/{invoice_id}/")
        assert fetched.status_code == 200
        assert Decimal(fetched.data["subtotal"]) == Decimal("525.50")

        # The live lookup now reports the enrollment as gone, without erroring.
        context = as_accountant_a.get(f"/api/v1/billing/invoices/{invoice_id}/enrollment/")
        assert context.status_code == 404
