"""
Billing use cases.

This is the only place in the billing context that talks to another context, and
it does so exclusively through :mod:`apps.academic.services` -- a function call
returning dataclasses, not an ORM traversal. Swapping that import for an HTTP
client is the entire cost of extracting billing into its own service.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from django.db import connection, transaction
from django.db.models import Max
from django.utils.translation import gettext_lazy as _

from apps.academic import services as academic_services
from apps.core.exceptions import BusinessRuleViolation
from apps.tenants.models import Currency

from .models import Invoice, InvoiceLine, InvoiceStatus, Payment

DEFAULT_PAYMENT_TERM_DAYS = 30


def current_tenant_currency() -> str:
    """The currency the current institution bills in.

    During a request ``connection.tenant`` is the ``Client`` resolved from the
    host and the answer is already in memory. Outside one -- management
    commands, scheduled jobs, tests -- ``schema_context`` installs a placeholder
    that knows only the schema name, so the row is read instead.

    That fallback query is the point. Reading the attribute off the placeholder
    yields ``None``, and defaulting ``None`` to a currency would quietly invoice
    a dollar-billing school in pesos: the amounts would look plausible and
    nothing would fail. ``Client`` lives in ``public``, which is on the search
    path from every schema, so this reads the right row from anywhere.
    """
    tenant = getattr(connection, "tenant", None)
    currency = getattr(tenant, "default_currency", None)
    if currency:
        return currency

    from apps.tenants.models import Client

    return (
        Client.objects.filter(schema_name=connection.schema_name)
        .values_list("default_currency", flat=True)
        .first()
        or Currency.MXN
    )


def generate_invoice_number(on: date | None = None) -> str:
    """Sequential, human-readable number scoped to the current schema/year.

    Uniqueness is per-tenant because the table lives in the tenant's schema, so
    two schools can both have ``INV-2026-000001``.
    """
    on = on or date.today()
    prefix = f"INV-{on.year}-"
    last = (
        Invoice.all_objects.filter(number__startswith=prefix)
        .aggregate(highest=Max("number"))
        .get("highest")
    )
    sequence = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{sequence:06d}"


@transaction.atomic
def create_invoice_for_enrollment(
    *,
    enrollment_id: UUID,
    lines: list[dict],
    issue_date: date | None = None,
    due_date: date | None = None,
    currency: str | None = None,
    issued_by_id: UUID | None = None,
    notes: str = "",
) -> Invoice:
    """Issue an invoice against an enrollment.

    The enrollment is validated and its labels captured through the academic
    context's service layer. Because there is no FK, this check is what keeps
    the reference honest -- so it is not optional.
    """
    if currency is None:
        currency = current_tenant_currency()

    snapshot = academic_services.get_enrollment_snapshot(enrollment_id)
    if snapshot is None:
        raise BusinessRuleViolation(_("The referenced enrollment does not exist."))
    if not snapshot.is_billable:
        raise BusinessRuleViolation(_("This enrollment is not in a billable state."))
    if not lines:
        raise BusinessRuleViolation(_("An invoice needs at least one line."))

    issue_date = issue_date or date.today()
    due_date = due_date or issue_date + timedelta(days=DEFAULT_PAYMENT_TERM_DAYS)
    if due_date < issue_date:
        raise BusinessRuleViolation(_("The due date cannot precede the issue date."))

    invoice = Invoice.objects.create(
        number=generate_invoice_number(issue_date),
        enrollment_id=snapshot.enrollment_id,
        student_id=snapshot.student_id,
        program_id=snapshot.program_id,
        student_name_snapshot=snapshot.student_full_name,
        program_name_snapshot=snapshot.program_name,
        status=InvoiceStatus.ISSUED,
        currency=currency,
        issue_date=issue_date,
        due_date=due_date,
        issued_by_id=issued_by_id,
        notes=notes,
    )

    InvoiceLine.objects.bulk_create(
        InvoiceLine(
            invoice=invoice,
            concept_id=line.get("concept_id"),
            description=line["description"],
            quantity=Decimal(str(line.get("quantity", "1.00"))),
            unit_price=Decimal(str(line["unit_price"])),
        )
        for line in lines
    )
    return invoice


@transaction.atomic
def register_payment(
    *,
    invoice: Invoice,
    amount: Decimal,
    method: str,
    received_on: date | None = None,
    reference: str = "",
    recorded_by_id: UUID | None = None,
) -> Payment:
    """Record a payment and move the invoice's status to match its balance."""
    if invoice.status in {InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT}:
        raise BusinessRuleViolation(_("Payments can only be recorded against an issued invoice."))
    if amount <= Decimal("0.00"):
        raise BusinessRuleViolation(_("The payment amount must be positive."))
    if amount > invoice.balance:
        raise BusinessRuleViolation(
            _("The payment exceeds the outstanding balance of the invoice.")
        )

    payment = Payment.objects.create(
        invoice=invoice,
        amount=amount,
        method=method,
        reference=reference,
        received_on=received_on or date.today(),
        recorded_by_id=recorded_by_id,
    )
    recalculate_invoice_status(invoice)
    return payment


def recalculate_invoice_status(invoice: Invoice) -> Invoice:
    """Derive status from the balance. Terminal states are left untouched."""
    if invoice.status in {InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT}:
        return invoice

    invoice.refresh_from_db()
    balance = invoice.balance

    if balance <= Decimal("0.00"):
        new_status = InvoiceStatus.PAID
    elif invoice.amount_paid > Decimal("0.00"):
        new_status = InvoiceStatus.PARTIALLY_PAID
    elif invoice.due_date < date.today():
        new_status = InvoiceStatus.OVERDUE
    else:
        new_status = InvoiceStatus.ISSUED

    if new_status != invoice.status:
        invoice.status = new_status
        invoice.save(update_fields=["status", "updated_at"])
    return invoice


def resolve_invoice_enrollments(invoices: list[Invoice]) -> dict[UUID, object]:
    """Batch-hydrate the academic side of a page of invoices.

    Used by list endpoints that want live enrollment status next to the stored
    snapshot, without a JOIN and without an N+1.
    """
    ids = [invoice.enrollment_id for invoice in invoices]
    return dict(academic_services.get_enrollment_snapshots(ids))
