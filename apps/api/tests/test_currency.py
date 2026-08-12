"""
The institution decides the currency, not the caller.

A school collects in one currency. Letting each invoice carry its own would
allow two invoices for the same student in different currencies with no
exchange rate to reconcile them, so the amount is denominated by the school's
``default_currency`` and the request may only confirm it.
"""

import pytest
from django_tenants.utils import schema_context

from apps.tenants.models import Currency
from conftest import PASSWORD, TENANT_A, tenant_setting

pytestmark = pytest.mark.django_db

_LINES = [{"description": "Matrícula anual", "unit_price": "1500.00", "quantity": "1"}]


def _payload(enrollment_id, **overrides) -> dict:
    return {"enrollment_id": str(enrollment_id), "lines": _LINES, **overrides}


class TestSchoolCurrency:
    def test_defaults_to_mexican_pesos(self, tenant_a):
        assert tenant_a.default_currency == Currency.MXN

    def test_login_reports_the_school_currency(self, api_a, admin_a):
        response = api_a.post(
            "/api/v1/auth/login/",
            {"email": admin_a.email, "password": PASSWORD},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["tenant"]["default_currency"] == Currency.MXN

    def test_the_currency_travels_in_the_access_token(self, api_a, admin_a):
        """So it survives a reload: a refresh returns only an access token."""
        from rest_framework_simplejwt.tokens import AccessToken

        response = api_a.post(
            "/api/v1/auth/login/",
            {"email": admin_a.email, "password": PASSWORD},
            format="json",
        )
        claims = AccessToken(response.data["access"])

        assert claims["tenant_currency"] == Currency.MXN

    def test_each_school_can_bill_in_a_different_currency(self, api_a, api_b, admin_a, admin_b):
        with tenant_setting("test_beta", default_currency=Currency.USD):
            a = api_a.post(
                "/api/v1/auth/login/",
                {"email": admin_a.email, "password": PASSWORD},
                format="json",
            )
            b = api_b.post(
                "/api/v1/auth/login/",
                {"email": admin_b.email, "password": PASSWORD},
                format="json",
            )

        assert a.data["tenant"]["default_currency"] == Currency.MXN
        assert b.data["tenant"]["default_currency"] == Currency.USD


class TestInvoicesInheritIt:
    def test_an_invoice_issued_without_a_currency_uses_the_school_setting(self, enrollment_a):
        from apps.billing.services import create_invoice_for_enrollment

        with schema_context(TENANT_A["schema"]):
            invoice = create_invoice_for_enrollment(enrollment_id=enrollment_a.id, lines=_LINES)

        assert invoice.currency == Currency.MXN

    def test_a_job_outside_a_request_still_reads_the_right_currency(self, enrollment_a):
        """`schema_context` gives no Client object -- the row must be read.

        This is the path management commands and scheduled jobs take. Guessing a
        default here would invoice a dollar-billing school in pesos, and every
        amount would still look plausible.
        """
        from apps.billing.services import create_invoice_for_enrollment

        with (
            tenant_setting(TENANT_A["schema"], default_currency=Currency.USD),
            schema_context(TENANT_A["schema"]),
        ):
            invoice = create_invoice_for_enrollment(enrollment_id=enrollment_a.id, lines=_LINES)

        assert invoice.currency == Currency.USD

    def test_the_api_issues_in_the_school_currency(self, as_accountant_a, enrollment_a):
        response = as_accountant_a.post(
            "/api/v1/billing/invoices/", _payload(enrollment_a.id), format="json"
        )

        assert response.status_code == 201, response.data
        assert response.data["currency"] == Currency.MXN

    def test_an_unsupported_currency_is_refused(self, as_accountant_a, enrollment_a):
        """Adding a currency is a decision -- formatting and rounding rules have
        to be written for it -- so free-form ISO codes are rejected."""
        response = as_accountant_a.post(
            "/api/v1/billing/invoices/",
            _payload(enrollment_a.id, currency="EUR"),
            format="json",
        )

        assert response.status_code == 400
        assert "currency" in response.data["error"]["details"]

    def test_an_explicit_supported_currency_is_still_honoured(self, as_accountant_a, enrollment_a):
        response = as_accountant_a.post(
            "/api/v1/billing/invoices/",
            _payload(enrollment_a.id, currency=Currency.USD),
            format="json",
        )

        assert response.status_code == 201, response.data
        assert response.data["currency"] == Currency.USD
