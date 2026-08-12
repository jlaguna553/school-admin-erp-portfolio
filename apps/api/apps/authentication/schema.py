"""
drf-spectacular extension for :class:`TenantJWTAuthentication`.

Without this, spectacular cannot recognise the custom authenticator and emits
the schema with *no* security scheme -- so generated clients (including
``packages/api-types``) would not know that endpoints need a Bearer token.

Importing this module is what registers the extension; see
``AuthenticationConfig.ready``.
"""

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class TenantJWTScheme(SimpleJWTScheme):
    target_class = "apps.authentication.authentication.TenantJWTAuthentication"
    name = "tenantJwtAuth"

    def get_security_requirement(self, auto_schema: object) -> dict[str, list[str]]:
        return {self.name: []}

    def get_security_definition(self, auto_schema: object) -> dict[str, object]:
        definition = super().get_security_definition(auto_schema)
        definition["description"] = (
            "JWT access token issued by `POST /api/v1/auth/login/`. The token is "
            "bound to the institution whose host issued it: presenting it to a "
            "different institution's host is rejected with 403 `tenant_mismatch`."
        )
        return definition
