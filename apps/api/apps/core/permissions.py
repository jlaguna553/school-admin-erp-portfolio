"""Reusable role-based permissions.

Roles travel in the JWT payload, but permissions are always checked against the
database row for the current schema -- a token claim is never trusted as the
sole authority for access.
"""

from typing import Any, ClassVar

from django.db import connection
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from . import modules, roles
from .exceptions import ModuleDisabled


class HasAnyRole(BasePermission):
    """Grant access when the user holds any of ``required_roles``.

    Subclass and set ``required_roles``::

        class IsRegistrar(HasAnyRole):
            required_roles = ("school_admin", "registrar")
    """

    required_roles: ClassVar[tuple[str, ...]] = ()

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        roles = getattr(view, "required_roles", None) or self.required_roles
        if not roles:
            return True
        return getattr(user, "role", None) in roles or user.is_superuser


class IsPlatformAdmin(BasePermission):
    """Only staff acting in the ``public`` schema (platform operators)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        is_public_schema = connection.schema_name == "public"
        return bool(user and user.is_authenticated and user.is_staff and is_public_schema)


class IsSchoolAdmin(HasAnyRole):
    required_roles: ClassVar[tuple[str, ...]] = ("school_admin",)


class ModulePermission(BasePermission):
    """Gate a viewset on its module: is it switched on, and may this role reach it?

    Two questions, two answers, and the order matters. A module the institution
    has switched off is refused for everyone including its administrator --
    otherwise "off" would mean "off for most people", which is not a setting
    anyone can reason about. Only then is the caller's role consulted.

    Subclass and set ``module``::

        class InvoiceViewSet(SoftDeleteModelViewSet):
            permission_classes = (ModulePermission,)
            module = Module.BILLING
    """

    module: ClassVar[str] = ""

    message = _("This module is not enabled for this institution.")

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False

        module = getattr(view, "module", None) or self.module
        if not module:
            # A viewset that forgot to name its module must not be reachable by
            # accident; failing closed is the only safe reading.
            return False

        tenant = getattr(connection, "tenant", None)
        if not modules.is_enabled(module, getattr(tenant, "disabled_modules", None)):
            raise ModuleDisabled()

        role = getattr(user, "role", None)
        if request.method in SAFE_METHODS:
            return modules.may_read(module, role)
        return modules.may_write(module, role)


class CanManageUser(BasePermission):
    """Object-level: you may act only on someone you outrank.

    Purely about rank, with no exception for yourself. Editing your own profile
    is a different operation with its own endpoint -- ``/users/me/`` -- which is
    open to every role precisely because it can only ever touch the caller.
    Allowing it here as well would have meant a student needing read access to
    the whole staff directory just to change their own phone number.

    Rank is what keeps the hierarchy honest: without it a coordinator could edit
    the administrator who appointed them.
    """

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return roles.outranks(getattr(user, "role", None), getattr(obj, "role", None))


class IsSelfOrSchoolAdmin(BasePermission):
    """Object-level: users may act on their own record; admins on anyone's."""

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or getattr(user, "role", None) == "school_admin":
            return True
        owner_id = getattr(obj, "user_id", None) or getattr(obj, "id", None)
        return owner_id == user.id
