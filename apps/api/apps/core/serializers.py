from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    """Response schema for the health probe."""

    status = serializers.CharField(read_only=True)
    schema = serializers.CharField(read_only=True)
    language = serializers.CharField(read_only=True)
    available_languages = serializers.ListField(child=serializers.CharField(), read_only=True)


class ErrorDetailSerializer(serializers.Serializer):
    """Documents the shape produced by ``apps.core.exceptions``."""

    code = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    details = serializers.DictField(read_only=True, required=False)


class ErrorEnvelopeSerializer(serializers.Serializer):
    error = ErrorDetailSerializer(read_only=True)


class BrandingSerializer(serializers.Serializer):
    """The institution's public identity, for an unauthenticated caller."""

    name = serializers.CharField(read_only=True)
    schema = serializers.CharField(read_only=True)
    brand_color = serializers.CharField(read_only=True)
    default_language = serializers.CharField(read_only=True)
