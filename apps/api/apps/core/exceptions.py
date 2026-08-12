"""
Domain exceptions and the single API error envelope.

Every error the API returns has the same shape, so the frontend needs exactly
one error handler:

    {
      "error": {
        "code": "validation_error",
        "message": "Los datos enviados no son válidos.",
        "details": {"email": ["Este campo es obligatorio."]}
      }
    }

Messages go through ``gettext``, so the body is rendered in the language
resolved for the request (``Accept-Language`` or the user's saved preference).
"""

import logging
from typing import Any

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException, Throttled
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# NOTE: ``rest_framework.views`` is imported lazily inside
# :func:`api_exception_handler`. Importing it here would deadlock at startup:
# DRF resolves ``DEFAULT_AUTHENTICATION_CLASSES`` (which points at
# ``apps.authentication``, which imports this module) *while*
# ``rest_framework.views`` is still initialising.


# ---------------------------------------------------------------------------
# Domain exceptions -- raised by services, translated at the boundary.
# ---------------------------------------------------------------------------
class DomainError(APIException):
    """Base class for business-rule violations."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("The operation could not be completed.")
    default_code = "domain_error"


class BusinessRuleViolation(DomainError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = _("This operation violates a business rule.")
    default_code = "business_rule_violation"


class ModuleDisabled(DomainError):
    """The institution has switched this part of the product off.

    Distinct from "you may not" on purpose: a 403 with its own code lets the
    interface say the module is unavailable here rather than implying the person
    lacks a permission they might go and ask for.
    """

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _("This module is not enabled for this institution.")
    default_code = "module_disabled"


class ResourceConflict(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _("The resource is in a state that conflicts with this request.")
    default_code = "resource_conflict"


class TenantMismatch(DomainError):
    """The token's tenant claim disagrees with the schema resolved from the host.

    A hard security boundary: it means a token issued for one school was
    presented to another, so it is always rejected and always logged.
    """

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _("This credential does not belong to the requested institution.")
    default_code = "tenant_mismatch"


# ---------------------------------------------------------------------------
# Exception handler
# ---------------------------------------------------------------------------
def _flatten_detail(detail: Any) -> tuple[str, Any]:
    """Split a DRF detail into a human message and a structured detail payload."""
    if isinstance(detail, dict):
        # DRF wraps a scalar detail as {"detail": "..."} for non-field errors
        # (403, 404, 429, custom APIExceptions). That is the message itself, not
        # a map of field errors -- surface it instead of the validation text.
        if set(detail) == {"detail"}:
            return str(detail["detail"]), None
        return str(_("The submitted data is invalid.")), detail
    if isinstance(detail, list):
        first = detail[0] if detail else _("An error occurred.")
        return str(first), detail
    return str(detail), None


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF ``EXCEPTION_HANDLER`` that normalises every error to one envelope."""
    from rest_framework.views import exception_handler as drf_exception_handler

    # Translate Django-native exceptions into their DRF equivalents first so
    # they get the same envelope instead of falling through to a 500.
    if isinstance(exc, DjangoValidationError):
        from rest_framework.exceptions import ValidationError as DRFValidationError

        exc = DRFValidationError(detail=getattr(exc, "message_dict", exc.messages))
    elif isinstance(exc, PermissionDenied):
        from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied

        exc = DRFPermissionDenied()
    elif isinstance(exc, Http404):
        from rest_framework.exceptions import NotFound

        exc = NotFound()

    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled -- let Django's 500 machinery report it, but log the view.
        logger.exception("Unhandled exception in %s", context.get("view"), exc_info=exc)
        return None

    if isinstance(exc, Throttled):
        # DRF's own Spanish string reads poorly ("Solicitud fue regulada
        # (throttled)"), and Spanish is this project's default language, so the
        # message is replaced with one from our catalogue.
        wait = exc.wait or 0
        response.data = {
            "detail": _("Too many attempts. Try again in %(seconds)s seconds.")
            % {"seconds": int(wait)}
        }

    if isinstance(exc, TenantMismatch):
        request = context.get("request")
        logger.warning(
            "Tenant mismatch rejected: path=%s host=%s",
            getattr(request, "path", "?"),
            request.get_host() if request is not None else "?",
        )

    code = getattr(exc, "default_code", "error")
    message, details = _flatten_detail(response.data)

    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details

    response.data = payload
    return response
