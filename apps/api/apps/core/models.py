"""
Abstract base models every bounded context builds on.

UUID primary keys are deliberate: they let a module be extracted into its own
service without renumbering, and they let distant contexts reference each other
by identifier (rule A.2) instead of by ForeignKey.
"""

import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import AllObjectsManager, SoftDeleteManager


class UUIDPrimaryKeyModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
    )

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name=_("created at")
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """Adds ``is_active`` + ``deleted_at`` and rewires deletion to deactivation."""

    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("active"))
    deleted_at = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name=_("deleted at")
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True
        base_manager_name = "all_objects"

    def delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:  # type: ignore[override]
        """Soft-delete this record. Physical deletion is never implicit."""
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(using=using, update_fields=["is_active", "deleted_at", "updated_at"])
        return 1, {self._meta.label: 1}

    def hard_delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        """Permanently remove this record. Retention jobs and tests only."""
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self) -> None:
        self.is_active = True
        self.deleted_at = None
        self.save(update_fields=["is_active", "deleted_at", "updated_at"])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class BaseModel(UUIDPrimaryKeyModel, TimeStampedModel, SoftDeleteModel):
    """UUID pk + timestamps + soft delete. The default base for domain models."""

    class Meta:
        abstract = True
        base_manager_name = "all_objects"
