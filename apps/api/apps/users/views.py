from typing import Any

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.modules import Module
from apps.core.permissions import CanManageUser, ModulePermission
from apps.core.roles import assignable_roles
from apps.core.viewsets import SoftDeleteModelViewSet

from .models import User, UserRole
from .serializers import (
    ChangePasswordSerializer,
    MeSerializer,
    UserCreateSerializer,
    UserRoleChoiceSerializer,
    UserSerializer,
)


@extend_schema_view(
    list=extend_schema(summary="List users at this institution"),
    destroy=extend_schema(
        summary="Deactivate a user",
        description="Soft delete -- the row is retained and login is blocked.",
    ),
)
class UserViewSet(SoftDeleteModelViewSet):
    """Users of the current institution.

    The queryset needs no tenant filter: the connection's ``search_path`` is
    already pinned to this school's schema by ``TenantJWTAuthentication``, from
    the caller's token.
    """

    queryset = User.objects.all()
    permission_classes = (ModulePermission,)
    module = Module.USERS
    filterset_fields = ("role", "is_active", "language")
    search_fields = ("email", "first_name", "last_name")
    ordering_fields = ("last_name", "email", "date_joined")

    def get_serializer_class(self) -> type[Any]:
        if self.action == "create":
            return UserCreateSerializer
        if self.action in {"me", "update_me"}:
            return MeSerializer
        if self.action == "change_password":
            return ChangePasswordSerializer
        if self.action == "roles":
            return UserRoleChoiceSerializer
        return UserSerializer

    def get_permissions(self) -> list[Any]:
        if self.action in {"me", "update_me", "change_password", "roles"}:
            return []
        if self.action in {"retrieve", "update", "partial_update"}:
            return [ModulePermission(), CanManageUser()]
        return super().get_permissions()

    @extend_schema(summary="Current user", responses={200: MeSerializer})
    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)

    @extend_schema(summary="Update current user", responses={200: MeSerializer})
    @me.mapping.patch
    def update_me(self, request: Request) -> Response:
        serializer = MeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(summary="Change own password", responses={204: None})
    @action(detail=False, methods=["post"], url_path="me/change-password")
    def change_password(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Available roles",
        description=(
            "Localised role labels, rendered in the request's language. Only "
            "roles the caller may actually assign are listed."
        ),
        responses={200: UserRoleChoiceSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="roles")
    def roles(self, request: Request) -> Response:
        # This endpoint exists so the frontend never hardcodes role labels,
        # which makes it the natural place to apply the hierarchy: a caller is
        # only offered roles strictly below their own. Offering more would
        # render options whose only possible outcome is a validation error, and
        # would advertise a privilege they do not have.
        allowed = set(assignable_roles(getattr(request.user, "role", None)))
        payload = [
            {"value": value, "label": str(label)}
            for value, label in UserRole.choices
            if value in allowed
        ]
        return Response(payload)
