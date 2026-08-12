from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _

from apps.core.managers import SoftDeleteQuerySet


class UserManager(BaseUserManager.from_queryset(SoftDeleteQuerySet)):  # type: ignore[misc]
    """Email-based user manager that also honours the soft-delete rule."""

    use_in_migrations = True

    def get_queryset(self) -> SoftDeleteQuerySet:
        return super().get_queryset().filter(deleted_at__isnull=True)

    def _create_user(self, email: str, password: str | None, **extra: Any) -> Any:
        if not email:
            raise ValueError(str(_("An email address is required.")))
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra: Any) -> Any:
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> Any:
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", "platform_admin")
        if extra.get("is_staff") is not True:
            raise ValueError(str(_("Superusers must have is_staff=True.")))
        if extra.get("is_superuser") is not True:
            raise ValueError(str(_("Superusers must have is_superuser=True.")))
        return self._create_user(email, password, **extra)


class AllUsersManager(BaseUserManager.from_queryset(SoftDeleteQuerySet)):  # type: ignore[misc]
    """Sees deactivated users too; used as ``base_manager_name``."""
