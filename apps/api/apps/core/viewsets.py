"""Base viewsets that wire in the project-wide conventions."""

from typing import Any

from django.utils import translation
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from .middleware import supported_language


class LocalePreferenceMixin:
    """Apply the authenticated user's language preference to API responses.

    Middleware cannot do this for API traffic: DRF authenticates inside
    ``initial()``, long after middleware has run. Hooking ``initial()`` means
    ``gettext`` calls in serializers, validators and services all render in the
    right language.

    Precedence matches :class:`apps.core.middleware.UserLanguageMiddleware`: an
    explicit ``Accept-Language`` header wins, so the frontend's language switcher
    takes effect immediately, and the stored profile preference is the fallback
    for clients that send no header.
    """

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)  # type: ignore[misc]

        if supported_language(request.headers.get("Accept-Language")):
            return  # LocaleMiddleware already honoured the explicit header.

        user = request.user
        language = supported_language(getattr(user, "language", None))
        if language and user.is_authenticated:
            translation.activate(language)
            request.LANGUAGE_CODE = language


class SoftDeleteModelViewSet(LocalePreferenceMixin, viewsets.ModelViewSet):
    """``ModelViewSet`` whose ``DELETE`` deactivates the record (rule A.3).

    ``BaseModel.delete()`` is already a soft delete, so ``perform_destroy`` needs
    no override -- but it is spelled out here so the behaviour is discoverable
    at the API layer rather than only in the model.
    """

    def perform_destroy(self, instance: Any) -> None:
        instance.delete()  # soft: sets is_active=False, deleted_at=now()

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().destroy(request, *args, **kwargs)


class ReadOnlyViewSet(LocalePreferenceMixin, viewsets.ReadOnlyModelViewSet):
    """List/retrieve only, with locale handling."""
