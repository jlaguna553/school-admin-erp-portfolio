"""Request-scoped i18n middleware."""

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils import translation


def supported_language(code: str | None) -> str | None:
    """Return ``code`` if the project serves it, else ``None``."""
    if not code:
        return None
    supported = {lang for lang, _label in settings.LANGUAGES}
    if code in supported:
        return code
    # Accept ``en-GB`` as ``en``.
    base = code.split("-")[0]
    return base if base in supported else None


class UserLanguageMiddleware:
    """Fall back to the authenticated user's saved language preference.

    Precedence, highest first:

    1. An explicit ``Accept-Language`` header naming a supported language.
       The frontend sends this on every call to match the locale in the URL, so
       switching language in the UI takes effect immediately -- without this
       taking priority, a stored preference would silently override the
       language the user just picked.
    2. The user's ``language`` profile field (this middleware). Applies to
       clients that send no header: mobile apps, background jobs, emails.
    3. ``settings.LANGUAGE_CODE`` (``es``).

    This covers session-authenticated traffic (Django admin, SSR). DRF resolves
    its user inside the view, after middleware has run, so API views apply the
    same rule via :class:`apps.core.viewsets.LocalePreferenceMixin`.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not supported_language(request.headers.get("Accept-Language")):
            user = getattr(request, "user", None)
            language = supported_language(getattr(user, "language", None))
            if language and getattr(user, "is_authenticated", False):
                translation.activate(language)
                request.LANGUAGE_CODE = language

        response = self.get_response(request)
        response.setdefault("Content-Language", translation.get_language() or "")
        return response
