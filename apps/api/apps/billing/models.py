"""
The billing bounded context: what a family owes and what they have paid.

**Rule A.2 in practice.** Billing is a *distant* domain from academic, so this
module contains no ForeignKey into ``apps.academic``. An invoice records
``enrollment_id``, ``student_id`` and ``program_id`` as plain UUIDs, plus a
denormalised copy of the labels it needs to print. Consequences, all deliberate:

* No cross-domain JOIN exists, so billing can be lifted into its own service
  and database without a schema migration.
* Reading academic facts goes through :mod:`apps.academic.services`, never the
  academic ORM.
* An invoice stays printable and auditable even if the enrollment is later
  withdrawn or renamed -- a financial record must not mutate retroactively.

The trade-off is that the database cannot enforce referential integrity here;
:mod:`apps.billing.services` validates the reference before an invoice is
created.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    ISSUED = "issued", _("Issued")
    PARTIALLY_PAID = "partially_paid", _("Partially paid")
    PAID = "paid", _("Paid")
    OVERDUE = "overdue", _("Overdue")
    CANCELLED = "cancelled", _("Cancelled")


class PaymentMethod(models.TextChoices):
    CASH = "cash", _("Cash")
    CARD = "card", _("Card")
    TRANSFER = "transfer", _("Bank transfer")
    CHEQUE = "cheque", _("Cheque")


class Invoice(BaseModel):
    number = models.CharField(max_length=32, unique=True, verbose_name=_("invoice number"))

    # --- Cross-context references: UUIDs only, never ForeignKeys (rule A.2) ---
    enrollment_id = models.UUIDField(
        db_index=True,
        verbose_name=_("enrollment ID"),
        help_text=_("Reference to apps.academic Enrollment. Resolved via services."),
    )
    student_id = models.UUIDField(db_index=True, verbose_name=_("student ID"))
    program_id = models.UUIDField(null=True, blank=True, verbose_name=_("programme ID"))

    # Denormalised labels captured at issue time so the document is immutable.
    student_name_snapshot = models.CharField(max_length=300, verbose_name=_("student name"))
    program_name_snapshot = models.CharField(
        max_length=200, blank=True, verbose_name=_("programme name")
    )

    # ``issued_by`` *is* a ForeignKey: identity is same-context, same schema.
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoices_issued",
        verbose_name=_("issued by"),
    )

    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
        db_index=True,
        verbose_name=_("status"),
    )
    currency = models.CharField(max_length=3, default="USD", verbose_name=_("currency"))
    issue_date = models.DateField(verbose_name=_("issue date"))
    due_date = models.DateField(db_index=True, verbose_name=_("due date"))
    notes = models.TextField(blank=True, verbose_name=_("notes"))

    class Meta:
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")
        ordering = ("-issue_date", "-number")
        indexes = (
            models.Index(fields=("student_id", "status")),
            models.Index(fields=("status", "due_date")),
        )
        constraints = (
            models.CheckConstraint(
                condition=models.Q(due_date__gte=models.F("issue_date")),
                name="invoice_due_after_issue",
            ),
        )

    def __str__(self) -> str:
        return f"{self.number} · {self.student_name_snapshot}"

    @property
    def subtotal(self) -> Decimal:
        return sum((line.line_total for line in self.lines.all()), start=Decimal("0.00"))

    @property
    def amount_paid(self) -> Decimal:
        return sum((payment.amount for payment in self.payments.all()), start=Decimal("0.00"))

    @property
    def balance(self) -> Decimal:
        return self.subtotal - self.amount_paid


class InvoiceLine(BaseModel):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name=_("invoice"),
    )
    # A fee concept may originate in the academic catalogue -- again by UUID.
    concept_id = models.UUIDField(null=True, blank=True, verbose_name=_("concept ID"))
    description = models.CharField(max_length=300, verbose_name=_("description"))
    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=(MinValueValidator(Decimal("0.01")),),
        verbose_name=_("quantity"),
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=(MinValueValidator(Decimal("0.00")),),
        verbose_name=_("unit price"),
    )

    class Meta:
        verbose_name = _("invoice line")
        verbose_name_plural = _("invoice lines")
        ordering = ("created_at",)

    def __str__(self) -> str:
        return self.description

    @property
    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


class Payment(BaseModel):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name=_("invoice"),
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=(MinValueValidator(Decimal("0.01")),),
        verbose_name=_("amount"),
    )
    method = models.CharField(
        max_length=16,
        choices=PaymentMethod.choices,
        default=PaymentMethod.TRANSFER,
        verbose_name=_("method"),
    )
    reference = models.CharField(max_length=120, blank=True, verbose_name=_("reference"))
    received_on = models.DateField(verbose_name=_("received on"))
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments_recorded",
        verbose_name=_("recorded by"),
    )

    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        ordering = ("-received_on",)

    def __str__(self) -> str:
        return f"{self.amount} {self.invoice.currency} · {self.invoice.number}"
