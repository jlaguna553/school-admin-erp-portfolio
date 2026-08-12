from typing import Any

from django.db import connection
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPlatformAdmin
from apps.core.viewsets import SoftDeleteModelViewSet

from .models import Membership, PlatformIdentity
from .serializers import (
    AvailableSchoolSerializer,
    MembershipSerializer,
    PlatformIdentityCreateSerializer,
    PlatformIdentitySerializer,
    SetIdentityPasswordSerializer,
)


@extend_schema_view(
    list=extend_schema(summary="List people with platform-wide credentials"),
    retrieve=extend_schema(summary="Retrieve a person and their schools"),
    create=extend_schema(summary="Create a platform identity"),
    destroy=extend_schema(
        summary="Deactivate a person",
        description=(
            "Soft delete. Blocks sign-in at every school at once, which is the "
            "point of a single credential -- revoking access no longer means "
            "hunting through each school's user list."
        ),
    ),
)
class PlatformIdentityViewSet(SoftDeleteModelViewSet):
    """People who may work at more than one school.

    Platform operators only, and public host only. The membership list is the
    sensitive part: it says which schools employ a given person, which no single
    school is entitled to read about another.
    """

    queryset = PlatformIdentity.objects.prefetch_related("memberships__tenant")
    permission_classes = (IsPlatformAdmin,)
    filterset_fields = ("is_active", "language")
    search_fields = ("email", "first_name", "last_name")
    ordering_fields = ("last_name", "email", "created_at")

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Respond with the full record, not the write-only input shape.

        The create serializer exists to accept a password; echoing it back would
        return a body with no ``id``, leaving a caller unable to do the obvious
        next thing -- grant the person their first school.
        """
        serializer = PlatformIdentityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identity = serializer.save()
        return Response(
            PlatformIdentitySerializer(identity).data,
            status=status.HTTP_201_CREATED,
        )

    def get_serializer_class(self) -> type[Any]:
        if self.action == "create":
            return PlatformIdentityCreateSerializer
        if self.action == "set_password":
            return SetIdentityPasswordSerializer
        if self.action in {"memberships", "revoke_membership"}:
            return MembershipSerializer
        return PlatformIdentitySerializer

    @extend_schema(
        summary="Reset a person's password",
        description="The recovery path when someone is locked out of every school.",
        responses={204: None},
    )
    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request: Request, pk: str | None = None) -> Response:
        identity = self.get_object()
        serializer = SetIdentityPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identity.set_password(serializer.validated_data["new_password"])
        identity.save(update_fields=["password", "updated_at"])
        # One credential, one place: nothing has to be propagated to the schools.
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Grant access to a school",
        request=MembershipSerializer,
        responses={201: MembershipSerializer},
    )
    @action(detail=True, methods=["post"], url_path="memberships")
    def memberships(self, request: Request, pk: str | None = None) -> Response:
        identity = self.get_object()
        serializer = MembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Re-granting access to a school the person was removed from reactivates
        # the original row rather than colliding with the uniqueness constraint.
        existing = Membership.all_objects.filter(
            identity=identity, tenant=serializer.validated_data["tenant"]
        ).first()
        if existing is not None:
            existing.role = serializer.validated_data["role"]
            existing.is_active = True
            existing.deleted_at = None
            existing.save(update_fields=["role", "is_active", "deleted_at", "updated_at"])
            membership = existing
        else:
            membership = serializer.save(identity=identity)

        return Response(
            MembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(summary="Revoke access to a school", responses={204: None})
    @action(
        detail=True,
        methods=["delete"],
        url_path="memberships/(?P<membership_id>[^/.]+)",
    )
    def revoke_membership(
        self, request: Request, pk: str | None = None, membership_id: str | None = None
    ) -> Response:
        identity = self.get_object()
        membership = get_object_or_404(Membership.all_objects, pk=membership_id, identity=identity)
        # Soft: the school's own user row survives with its history intact, but
        # the person can no longer sign in there.
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AvailableSchoolsView(APIView):
    """Where else the signed-in person can work.

    Served on a *school's* host, not the platform's: it answers for whoever is
    currently signed in. It reads the public schema's membership table, which is
    on the search path from every schema, and returns nothing at all for an
    account with no platform identity -- so a single-school user learns nothing
    about the platform's structure.
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = AvailableSchoolSerializer

    @extend_schema(
        summary="Schools the signed-in person can reach",
        description=(
            "Every school the caller may work at, current one included. Empty "
            "for a platform operator. Each entry carries the school's currency "
            "and brand colour so the client can repaint immediately after "
            "switching, without a second round trip."
        ),
        responses={200: AvailableSchoolSerializer(many=True)},
    )
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        identity_id = getattr(request.user, "identity_id", None)
        if not identity_id:
            return Response([])

        identity = PlatformIdentity.objects.filter(pk=identity_id).first()
        if identity is None:
            return Response([])

        from apps.identity import services as identity_services

        current = connection.schema_name
        return Response(
            [
                identity_services.school_payload(membership, current)
                for membership in identity.schools()
            ]
        )
