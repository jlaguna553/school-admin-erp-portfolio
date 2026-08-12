from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.core import modules

from .models import Client, Domain

# Postgres refuses to create a schema with one of these names, and two of them
# would collide with the platform's own.
RESERVED_SCHEMA_NAMES = frozenset({"public", "information_schema", "pg_catalog", "pg_toast"})

# Postgres truncates identifiers past this, which would silently merge two
# schools whose names share a long prefix.
MAX_SCHEMA_NAME_LENGTH = 48


def derive_schema_name(name: str) -> str:
    """Turn an institution's name into a usable Postgres schema name.

    Derived rather than asked for. The schema is how the data is isolated, not
    something an operator opening a new school has an opinion about, and asking
    invited two failure modes: a name Postgres rejects, and one that collides
    with an existing school -- both surfacing as errors at the end of a slow
    provisioning call.

    Accents and punctuation are folded away, and a leading digit is prefixed,
    because an identifier must start with a letter. If the result is already
    taken a counter is appended, so two schools genuinely called "San José" both
    get provisioned instead of the second one failing.
    """
    from django.utils.text import slugify

    base = slugify(name).replace("-", "_").strip("_")[:MAX_SCHEMA_NAME_LENGTH]
    if not base or base[0].isdigit():
        # `slugify` strips anything unusable, so a name written entirely in a
        # non-Latin script can legitimately reduce to nothing.
        base = f"t_{base}" if base else "school"
    if base in RESERVED_SCHEMA_NAMES:
        base = f"{base}_school"

    candidate = base
    suffix = 2
    while Client.objects.filter(schema_name=candidate).exists():
        candidate = f"{base[: MAX_SCHEMA_NAME_LENGTH - 4]}_{suffix}"
        suffix += 1

    return candidate


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ("id", "domain", "is_primary")
        read_only_fields = ("id",)


class ClientSerializer(serializers.ModelSerializer):
    domains = DomainSerializer(many=True, read_only=True)
    # Derived, so a client never has to know that the stored list is the
    # inverse of the useful one.
    enabled_modules = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = (
            "id",
            "name",
            "legal_name",
            "tax_id",
            "schema_name",
            "default_language",
            "default_currency",
            "brand_color",
            "disabled_modules",
            "enabled_modules",
            "timezone",
            "on_trial",
            "paid_until",
            "is_active",
            "domains",
            "created_at",
        )
        read_only_fields = ("id", "is_active", "created_at", "domains", "enabled_modules")

    def get_enabled_modules(self, obj: Client) -> list[str]:
        return modules.enabled_modules(obj.disabled_modules)

    def validate_disabled_modules(self, value: list[str]) -> list[str]:
        """Refuse to switch off something the product cannot run without.

        The field is a plain array, so nothing else stops an operator disabling
        `users` and leaving a school nobody can administer -- including
        themselves.
        """
        fixed = [
            key for key in value if key in modules.MODULES and not modules.MODULES[key].optional
        ]
        if fixed:
            raise serializers.ValidationError(
                _("These modules cannot be switched off: %(names)s.") % {"names": ", ".join(fixed)}
            )
        # An unknown key needs no check here: the array's own `choices` reject
        # it first, per element.
        return value


class ClientProvisionSerializer(serializers.ModelSerializer):
    """Input for onboarding a school: a name and some preferences.

    Neither a hostname nor a schema name is asked for. One domain serves the
    whole platform, so a school is not reached at an address of its own -- it is
    selected by whoever signs in. And the Postgres schema is an implementation
    detail of how the data is isolated, not a decision an operator opening a new
    institution should have to make; it is derived from the name and reported
    back read-only.
    """

    schema_name = serializers.CharField(read_only=True)

    class Meta:
        model = Client
        fields = (
            "name",
            "legal_name",
            "tax_id",
            "schema_name",
            "default_language",
            "default_currency",
            "brand_color",
            "timezone",
        )

    def create(self, validated_data: dict[str, Any]) -> Client:
        # Creating the Client runs the schema migrations (auto_create_schema),
        # which is why this call is slower than an ordinary create.
        validated_data["schema_name"] = derive_schema_name(validated_data["name"])
        return Client.objects.create(**validated_data)
