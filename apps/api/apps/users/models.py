"""
Identity for the platform.

``apps.users`` is installed in both ``SHARED_APPS`` and ``TENANT_APPS``, so the
table exists once in ``public`` (platform operators) and once per school schema
(staff, teachers, students, guardians). A person enrolled at two schools is two
independent rows -- which is the point: one school can never enumerate another's
users, because the rows are not in the same schema.

Consequently ``email`` is unique *within a schema*, not globally.
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel

from .managers import AllUsersManager, UserManager


class UserRole(models.TextChoices):
    """Coarse-grained role. Fine-grained rules use Django permissions/groups.

    The role is embedded in the JWT so the frontend can render the right
    navigation without an extra request, but every authorization decision is
    re-checked server-side against this column.
    """

    PLATFORM_ADMIN = "platform_admin", _("Platform administrator")
    SCHOOL_ADMIN = "school_admin", _("School administrator")
    COORDINATOR = "coordinator", _("Academic coordinator")
    TEACHER = "teacher", _("Teacher")
    STUDENT = "student", _("Student")
    GUARDIAN = "guardian", _("Guardian")
    ACCOUNTANT = "accountant", _("Accountant")


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(unique=True, verbose_name=_("email address"))
    first_name = models.CharField(max_length=150, verbose_name=_("first name"))
    last_name = models.CharField(max_length=150, verbose_name=_("last name"))
    phone = models.CharField(max_length=32, blank=True, verbose_name=_("phone"))

    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
        db_index=True,
        verbose_name=_("role"),
    )

    # Drives translated API responses; the frontend mirrors it in the URL locale.
    language = models.CharField(
        max_length=5,
        choices=[("es", _("Spanish")), ("en", _("English"))],
        default="es",
        verbose_name=_("preferred language"),
    )

    is_staff = models.BooleanField(
        default=False,
        verbose_name=_("staff status"),
        help_text=_("Designates whether the user can log into the admin site."),
    )
    # Soft-delete pair (rule A.3). ``is_active`` doubles as Django's
    # authentication gate, so deactivating a user also blocks login.
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("active"))
    deleted_at = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name=_("deleted at")
    )

    # Links this school-local row to the person's single platform credential.
    #
    # A bare UUID rather than a ForeignKey, because the target lives in the
    # public schema while this row lives in the school's -- the same
    # cross-boundary reference rule A.2 mandates between billing and academic.
    # Null for accounts that exist only at this school, which is every account
    # created before cross-school access was introduced and every one created
    # directly on a school's own users screen.
    identity_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("platform identity"),
        help_text=_("Set when the person signs in with a platform-wide credential."),
    )

    date_joined = models.DateTimeField(default=timezone.now, verbose_name=_("date joined"))

    objects = UserManager()
    all_objects = AllUsersManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ("last_name", "first_name")
        base_manager_name = "all_objects"

    def __str__(self) -> str:
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        return self.first_name

    def delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:  # type: ignore[override]
        """Soft delete: deactivates and anonymises nothing. Never drops the row."""
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["is_active", "deleted_at", "updated_at"])
        return 1, {self._meta.label: 1}

    def hard_delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self) -> None:
        self.is_active = True
        self.deleted_at = None
        self.save(update_fields=["is_active", "deleted_at", "updated_at"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def roles(self) -> list[str]:
        """Roles for the JWT payload: the primary role plus group memberships."""
        groups = list(self.groups.values_list("name", flat=True))
        return [self.role, *groups]
