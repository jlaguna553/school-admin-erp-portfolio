from typing import Any

from django.shortcuts import get_object_or_404
from django_tenants.utils import schema_context
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.permissions import IsPlatformAdmin
from apps.core.viewsets import SoftDeleteModelViewSet
from apps.users.models import User
from apps.users.serializers import UserCreateSerializer, UserSerializer

from .models import Client
from .serializers import ClientProvisionSerializer, ClientSerializer


@extend_schema_view(
    list=extend_schema(summary="List institutions"),
    retrieve=extend_schema(summary="Retrieve an institution"),
    create=extend_schema(
        summary="Provision an institution",
        description=(
            "Creates the institution and its dedicated Postgres schema. Schema "
            "creation runs the full tenant migration set, so this call is slower "
            "than a normal create. No hostname is involved: one domain serves "
            "every school, and which one a request is for comes from the token."
        ),
    ),
    destroy=extend_schema(
        summary="Deactivate an institution",
        description=(
            "Soft delete: the institution is deactivated but its schema and data "
            "are preserved. Dropping the schema is a separate operational task."
        ),
    ),
)
class ClientViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Platform-operator API for onboarding and managing institutions.

    Shares a hostname with everything else, so ``IsPlatformAdmin`` is the whole
    of the separation: it requires the caller to be platform staff acting on the
    public schema, which a school's session never is.
    """

    queryset = Client.objects.all()
    permission_classes = (IsPlatformAdmin,)
    filterset_fields = ("is_active", "on_trial", "default_language")
    search_fields = ("name", "legal_name", "schema_name")
    ordering_fields = ("name", "created_at")

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Respond with the full record, not the provisioning input shape.

        The provisioning serializer exists to accept a name and derive a schema
        from it; echoing it back would return a body with no ``id``, leaving the
        console unable to do the obvious next thing -- open the new school and
        add its first administrator.
        """
        serializer = ClientProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client = serializer.save()
        return Response(ClientSerializer(client).data, status=status.HTTP_201_CREATED)

    def get_serializer_class(self) -> type[Any]:
        if self.action == "create":
            return ClientProvisionSerializer
        return ClientSerializer

    def perform_destroy(self, instance: Client) -> None:
        instance.delete()  # soft: keeps the schema


@extend_schema_view(
    list=extend_schema(summary="List the users of one institution"),
    retrieve=extend_schema(summary="Retrieve a user of one institution"),
    create=extend_schema(summary="Create a user at one institution"),
    partial_update=extend_schema(summary="Update a user, including their role"),
    destroy=extend_schema(
        summary="Deactivate a user of one institution",
        description="Soft delete -- the row is retained and login is blocked.",
    ),
)
class ClientUserViewSet(SoftDeleteModelViewSet):
    """Platform-operator access to the users *inside* a given institution.

    This is the one place where a platform operator reads and writes data
    belonging to a school without holding a session there. It exists so a
    locked-out institution can be recovered -- create the first administrator,
    fix a role, deactivate an account.

    The schema switch is deliberately narrow. Authentication and the
    ``IsPlatformAdmin`` check run first, against the *public* schema, because
    that is where platform staff live; entering the school's schema any earlier
    would look the caller's own token up in the school's user table and either
    reject a valid operator or, worse, match a different person with the same
    id. Only once the caller is known to be a platform operator does the
    connection move into the target schema, and it moves back in
    ``finalize_response`` -- by which point every serializer has already been
    evaluated, so nothing is left to read from the wrong schema.

    Granting ``platform_admin`` is still refused here, by the same validator the
    school's own endpoint uses: that role only means anything in the public
    schema, so a copy of it sitting in a school's table would be a confusing
    no-op rather than a privilege.
    """

    queryset = User.objects.all()
    permission_classes = (IsPlatformAdmin,)
    filterset_fields = ("role", "is_active", "language")
    search_fields = ("email", "first_name", "last_name")
    ordering_fields = ("last_name", "email", "date_joined")

    def get_serializer_class(self) -> type[Any]:
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)

        # Resolved while still in the public schema -- Client only exists there.
        client = get_object_or_404(Client, pk=self.kwargs["client_pk"], is_active=True)
        self.client_obj = client
        self._schema_ctx = schema_context(client.schema_name)
        self._schema_ctx.__enter__()

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        response = super().finalize_response(request, response, *args, **kwargs)
        # Runs even when the handler raised: DRF turns exceptions into responses
        # before calling this, so the connection cannot be stranded pointing at
        # a school's schema for whatever the worker serves next.
        ctx = getattr(self, "_schema_ctx", None)
        if ctx is not None:
            ctx.__exit__(None, None, None)
            self._schema_ctx = None
        return response
