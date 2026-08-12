from typing import Any

from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import User, UserRole


class AssignableRoleMixin:
    """Nobody may hand out a role at or above their own.

    This is the hierarchy's teeth. Without it the users endpoint would let
    anyone with write access appoint a school administrator -- or a platform
    operator -- and the ladder would describe the interface rather than
    constrain it.

    A peer role is withheld along with the ones above: granting it is
    indistinguishable from self-promotion the moment the appointee returns the
    favour.

    Requests with no acting user fall back to refusing everything above a school
    administrator, which is the case for the operator console creating a
    school's first administrator.
    """

    def validate_role(self, value: str) -> str:
        from django.db import connection

        from apps.core.roles import assignable_roles

        # Two independent rules, and both are needed.
        #
        # This one is about *context*: `platform_admin` is authority above every
        # institution, not a role a school has. A copy of it sitting in a
        # school's table would confer nothing and read as an escalation to
        # anyone auditing later -- so it is refused here even for an operator,
        # who is otherwise allowed to appoint their own equal.
        if value == UserRole.PLATFORM_ADMIN and connection.schema_name != "public":
            raise serializers.ValidationError(
                _("Platform administration is not a role within an institution.")
            )

        # And this one is about *rank*: nobody hands out a role at or above
        # their own.
        request = self.context.get("request")
        actor_role = getattr(getattr(request, "user", None), "role", None)

        if actor_role is None:
            allowed = assignable_roles(UserRole.PLATFORM_ADMIN)
        else:
            allowed = assignable_roles(actor_role)

        if value not in allowed:
            raise serializers.ValidationError(_("You cannot grant a role at or above your own."))
        return value


class UserSerializer(AssignableRoleMixin, serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "role",
            "language",
            "is_active",
            "date_joined",
        )
        read_only_fields = ("id", "is_active", "date_joined")


class UserCreateSerializer(AssignableRoleMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "phone",
            "role",
            "language",
            "password",
        )

    def validate_email(self, value: str) -> str:
        """The address must be free platform-wide, not just at this school.

        It used to only have to be unique within the schema, because the
        hostname disambiguated: two schools could each have their own
        ``ana@example.com``. One domain removes that, since the login form has
        nothing but the address to identify a person by.

        The message deliberately does not say *where* the address is taken. A
        school administrator has no business learning that someone works at
        another institution, and "already exists at this institution" would
        answer that question every time it was wrong.
        """
        from apps.identity.models import PlatformIdentity

        normalised = value.strip().lower()
        taken = (
            User.all_objects.filter(email__iexact=normalised).exists()
            or PlatformIdentity.all_objects.filter(email__iexact=normalised).exists()
        )
        if taken:
            raise serializers.ValidationError(_("This email address is not available."))
        return normalised

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    def create(self, validated_data: dict[str, Any]) -> User:
        """Create the person, their access to this school, and the local row.

        All three, because on a single domain a school-local row on its own is
        an account nobody can sign in to: the credential is looked up
        platform-wide, so a user without a :class:`PlatformIdentity` is
        invisible to the login form.
        """
        from apps.identity.services import provision_school_member

        password = validated_data.pop("password")
        return provision_school_member(password=password, **validated_data)


class MeSerializer(serializers.ModelSerializer):
    """The authenticated user's own record -- role is read-only here."""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "role",
            "language",
            "permissions",
        )
        read_only_fields = ("id", "email", "role")

    def get_permissions(self, obj: User) -> list[str]:
        return sorted(obj.get_all_permissions())


class ChangePasswordSerializer(serializers.Serializer):
    """Change your own password.

    The credential lives in the public schema, on the person's
    :class:`PlatformIdentity` -- the school-local row deliberately has an
    unusable password so there is only ever one thing to change. Writing here
    therefore changes the password at every school at once, which is what a
    single credential means.

    Platform operators have no identity: they are ordinary users of the public
    schema, and the password on their row is the real one.
    """

    current_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def _credential(self) -> Any:
        from apps.identity.models import PlatformIdentity

        user = self.context["request"].user
        identity_id = getattr(user, "identity_id", None)
        if identity_id:
            identity = PlatformIdentity.objects.filter(pk=identity_id).first()
            if identity is not None:
                return identity
        return user

    def validate_current_password(self, value: str) -> str:
        if not self._credential().check_password(value):
            raise serializers.ValidationError(_("The current password is incorrect."))
        return value

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value, self.context["request"].user)
        return value

    def save(self, **kwargs: Any) -> Any:
        credential = self._credential()
        credential.set_password(self.validated_data["new_password"])
        credential.save(update_fields=["password", "updated_at"])
        return credential


class UserRoleChoiceSerializer(serializers.Serializer):
    """Localised role list so the frontend does not hardcode labels."""

    value = serializers.ChoiceField(choices=UserRole.choices, read_only=True)
    label = serializers.CharField(read_only=True)
