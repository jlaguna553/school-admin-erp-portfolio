"""
Managers and querysets that enforce the project-wide soft-delete rule.

Architectural rule A.3: records are never physically removed. ``.delete()`` is
overridden all the way down to the queryset so that bulk operations cannot
bypass it either -- ``Model.objects.filter(...).delete()`` soft-deletes too.
"""

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """A queryset whose ``delete()`` deactivates instead of destroying."""

    def delete(self) -> tuple[int, dict[str, int]]:
        """Soft-delete every row in the queryset."""
        count = self.update(is_active=False, deleted_at=timezone.now())
        return count, {self.model._meta.label: count}

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        """Permanently remove rows. Reserved for data-retention jobs and tests."""
        return super().delete()

    def alive(self) -> "SoftDeleteQuerySet":
        return self.filter(deleted_at__isnull=True)

    def dead(self) -> "SoftDeleteQuerySet":
        return self.filter(deleted_at__isnull=False)

    def restore(self) -> int:
        return self.update(is_active=True, deleted_at=None)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):  # type: ignore[misc]
    """Default manager: only ever returns live rows."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager.from_queryset(SoftDeleteQuerySet)):  # type: ignore[misc]
    """Escape hatch that also sees soft-deleted rows.

    Used as ``base_manager_name`` so that following a ForeignKey to a
    soft-deleted parent still resolves instead of raising ``DoesNotExist``.
    """
