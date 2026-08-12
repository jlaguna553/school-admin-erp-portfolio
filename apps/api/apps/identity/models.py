"""
Who a person is, independent of any one school.

The rest of the ERP is schema-per-tenant: a user row lives inside a school's
schema, which is what makes every query tenant-safe without a ``tenant_id``
filter. That works until the same person works at two schools -- then they are
two unrelated rows with two passwords, and changing one does nothing to the
other.

This module puts the *credential* in the public schema exactly once, and records
membership of each school explicitly. The per-schema ``users.User`` row stays
where it is, because everything else in the system points at it: enrollments,
invoices, who issued what. It gains a bare ``identity_id`` UUID -- a reference
across a context boundary, which is the same pattern rule A.2 already mandates
between billing and academic.
"""

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.users.models import UserRole


class PlatformIdentity(BaseModel):
    """One person, one password, across every school they work at.

    Deliberately *not* Django's ``AUTH_USER_MODEL``. That is still the
    per-schema ``users.User``, so admin, permissions and every existing
    relationship keep working untouched; this model only answers "are these
    credentials valid, and who do they belong to".
    """

    email = models.EmailField(unique=True, verbose_name=_("email address"))
    first_name = models.CharField(max_length=150, verbose_name=_("first name"))
    last_name = models.CharField(max_length=150, verbose_name=_("last name"))
    phone = models.CharField(max_length=32, blank=True, verbose_name=_("phone"))

    language = models.CharField(
        max_length=5,
        choices=[("es", _("Spanish")), ("en", _("English"))],
        default="es",
        verbose_name=_("preferred language"),
    )

    password = models.CharField(max_length=128, verbose_name=_("password"))
    last_login = models.DateTimeField(null=True, blank=True, verbose_name=_("last login"))

    # Which school to open on the next sign-in. Remembered so that someone who
    # works mostly at one place is not asked to choose every morning; it is a
    # convenience, never an authority -- the membership is re-checked anyway.
    last_tenant = models.ForeignKey(
        "tenants.Client",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("last institution used"),
    )

    class Meta:
        verbose_name = _("platform identity")
        verbose_name_plural = _("platform identities")
        ordering = ("last_name", "first_name")
        base_manager_name = "all_objects"

    def __str__(self) -> str:
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def set_password(self, raw_password: str) -> None:
        """Hash with the project's configured hasher -- never store the raw value."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    def touch_login(self) -> None:
        self.last_login = timezone.now()
        self.save(update_fields=["last_login", "updated_at"])

    def schools(self) -> models.QuerySet:
        """Active memberships at active institutions, ordered by school name."""
        return (
            self.memberships.filter(is_active=True, tenant__is_active=True)
            .select_related("tenant")
            .order_by("tenant__name")
        )


class Membership(BaseModel):
    """Permission for one identity to act at one school, in one role.

    The ForeignKey to ``tenants.Client`` is intentional and does not breach rule
    A.2: both models live in the public schema and both are platform-level
    concerns, so there is no distant context to decouple from. The boundary that
    *is* crossed -- into a school's own schema -- is expressed as a UUID on
    ``users.User.identity_id``, with no FK, exactly as the rule requires.
    """

    identity = models.ForeignKey(
        PlatformIdentity,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("identity"),
    )
    tenant = models.ForeignKey(
        "tenants.Client",
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("institution"),
    )
    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.SCHOOL_ADMIN,
        verbose_name=_("role"),
    )

    class Meta:
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")
        ordering = ("tenant__name",)
        base_manager_name = "all_objects"
        constraints = (
            models.UniqueConstraint(
                fields=("identity", "tenant"),
                name="unique_identity_per_tenant",
            ),
        )

    def __str__(self) -> str:
        return f"{self.identity.email} @ {self.tenant.name} ({self.role})"
