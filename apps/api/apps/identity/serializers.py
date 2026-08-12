from typing import Any

from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.users.models import UserRole

from .models import Membership, PlatformIdentity


class MembershipSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_schema = serializers.CharField(source="tenant.schema_name", read_only=True)

    class Meta:
        model = Membership
        fields = (
            "id",
            "tenant",
            "tenant_name",
            "tenant_schema",
            "role",
            "is_active",
        )
        read_only_fields = ("id", "is_active")

    def validate_role(self, value: str) -> str:
        if value == UserRole.PLATFORM_ADMIN:
            raise serializers.ValidationError(
                _(
                    "Platform administration is not a membership of a school. "
                    "Grant it on a platform account instead."
                )
            )
        return value


class PlatformIdentitySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    memberships = MembershipSerializer(many=True, read_only=True)

    class Meta:
        model = PlatformIdentity
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "language",
            "memberships",
            "is_active",
            "last_login",
            "created_at",
        )
        read_only_fields = ("id", "is_active", "last_login", "created_at", "memberships")


class PlatformIdentityCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = PlatformIdentity
        fields = ("email", "first_name", "last_name", "phone", "language", "password")

    def validate_email(self, value: str) -> str:
        normalised = value.strip().lower()
        if PlatformIdentity.all_objects.filter(email__iexact=normalised).exists():
            raise serializers.ValidationError(_("A platform identity with this email exists."))
        return normalised

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    def create(self, validated_data: dict[str, Any]) -> PlatformIdentity:
        password = validated_data.pop("password")
        identity = PlatformIdentity(**validated_data)
        identity.set_password(password)
        identity.save()
        return identity


class SetIdentityPasswordSerializer(serializers.Serializer):
    """Operator-initiated password reset.

    Unlike a school's user endpoint -- where only the account owner may change a
    password -- this one exists because the platform operator is the recovery
    path when someone is locked out of every school at once.
    """

    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_new_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value


class AvailableSchoolSerializer(serializers.Serializer):
    """One entry in "which schools can I sign in to", for the school switcher."""

    tenant_id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    schema = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)
    default_currency = serializers.CharField(read_only=True)
    brand_color = serializers.CharField(read_only=True)
    modules = serializers.ListField(child=serializers.CharField(), read_only=True)
    is_current = serializers.BooleanField(read_only=True)
