"""
The tenant registry. Lives only in the ``public`` schema.

Each :class:`Client` owns one Postgres schema containing that school's entire
dataset, which is why no application query ever needs a ``tenant_id`` filter.

Which schema a request uses is decided by the caller's access token, not by the
hostname: one domain serves the whole platform. :class:`Domain` survives because
``django-tenants`` requires ``TENANT_DOMAIN_MODEL`` to point somewhere, and
because the public schema still records the address the platform answers on --
but nothing routes by it any more.
"""

import uuid

from django.contrib.postgres.fields import ArrayField
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_tenants.models import DomainMixin, TenantMixin

from apps.core.modules import Module


class Currency(models.TextChoices):
    """Currencies the platform bills in.

    Deliberately a short, explicit list rather than free-form ISO codes: every
    supported currency needs formatting, rounding and (eventually) tax rules
    that have to be written, so adding one is a decision, not configuration.
    """

    MXN = "MXN", _("Mexican peso")
    USD = "USD", _("US dollar")


class Client(TenantMixin):
    """A school / institution.

    Deliberately does **not** use :class:`apps.core.models.SoftDeleteModel`.
    That mixin installs a default manager which hides deactivated rows, and
    ``migrate_schemas`` iterates the default manager -- a deactivated school
    would silently stop receiving migrations and drift from the codebase.
    Instead the soft-delete contract is implemented explicitly below while the
    default manager keeps returning every row.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=200, verbose_name=_("name"))
    legal_name = models.CharField(max_length=255, blank=True, verbose_name=_("legal name"))
    tax_id = models.CharField(max_length=50, blank=True, verbose_name=_("tax ID"))

    # Per-institution i18n/locale defaults. A user without an explicit
    # preference inherits these.
    default_language = models.CharField(
        max_length=5,
        default="es",
        choices=[("es", _("Spanish")), ("en", _("English"))],
        verbose_name=_("default language"),
    )
    timezone = models.CharField(max_length=64, default="UTC", verbose_name=_("timezone"))

    # Every amount the institution bills is denominated in this. Kept on the
    # institution rather than asked per invoice because a school collects in one
    # currency: making it per-invoice would invite two invoices for the same
    # student in different currencies with no exchange rate to reconcile them.
    default_currency = models.CharField(
        max_length=3,
        default=Currency.MXN,
        choices=Currency.choices,
        verbose_name=_("default currency"),
        help_text=_("Currency used for every invoice issued by this institution."),
    )

    # The institution's brand colour, as `#rrggbb`.
    #
    # One colour rather than a full theme on purpose: the interface derives
    # `--primary`, `--ring`, `--accent`, the dark-mode variant and the
    # contrasting text colour from it. An operator configuring six colours by
    # hand can produce an unreadable interface; deriving them cannot.
    brand_color = models.CharField(
        max_length=7,
        default="#1d4ed8",
        validators=[
            RegexValidator(
                regex=r"^#[0-9a-fA-F]{6}$",
                message=_("Use a six-digit hex colour, e.g. #1d4ed8."),
            )
        ],
        verbose_name=_("brand colour"),
        help_text=_("Six-digit hex. The rest of the palette is derived from it."),
    )

    # Modules this institution has switched **off**.
    #
    # Storing the exceptions rather than the selection is the point: a module
    # shipped in a later release is then live everywhere by default, instead of
    # missing from every school provisioned before it existed. An "enabled" list
    # would need a data migration on every release to avoid exactly that.
    disabled_modules = ArrayField(
        base_field=models.CharField(max_length=32, choices=Module.choices),
        default=list,
        blank=True,
        verbose_name=_("disabled modules"),
        help_text=_("Modules switched off for this institution. Empty means all are on."),
    )

    # Subscription bookkeeping (platform-level, not the billing context).
    on_trial = models.BooleanField(default=True, verbose_name=_("on trial"))
    paid_until = models.DateField(null=True, blank=True, verbose_name=_("paid until"))

    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("active"))
    deleted_at = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name=_("deleted at")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))

    # Create the schema automatically when a school is provisioned...
    auto_create_schema = True
    # ...but never destroy one implicitly. Dropping a school's data must be a
    # deliberate, separate operation.
    auto_drop_schema = False

    class Meta:
        verbose_name = _("institution")
        verbose_name_plural = _("institutions")
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.schema_name})"

    def delete(self, force_drop: bool = False, *args, **kwargs):  # type: ignore[override]
        """Deactivate the institution; keep its schema and data intact.

        ``force_drop=True`` delegates to ``TenantMixin.delete``, which drops the
        schema. That path exists for data-retention and test teardown only.
        """
        if force_drop:
            return super().delete(*args, force_drop=True, **kwargs)

        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at", "updated_at"])
        return 1, {self._meta.label: 1}

    def restore(self) -> None:
        self.is_active = True
        self.deleted_at = None
        self.save(update_fields=["is_active", "deleted_at", "updated_at"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class Domain(DomainMixin):
    """A hostname that resolves to a :class:`Client`.

    ``DomainMixin`` supplies ``domain``, ``is_primary`` and the ``tenant`` FK.
    In development schools are reached at ``<schema>.localhost:8000``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        verbose_name = _("domain")
        verbose_name_plural = _("domains")

    def __str__(self) -> str:
        return self.domain
