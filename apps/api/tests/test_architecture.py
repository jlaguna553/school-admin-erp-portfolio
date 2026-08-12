"""
Architecture guard tests.

These enforce the project's structural rules mechanically instead of by code
review. They are pure introspection over Django's model registry -- no database,
no fixtures -- so they run in milliseconds and fail the build the moment someone
adds a shortcut that would make a module impossible to extract.

Rules under test:
* A.2 -- no ORM relationship between distant bounded contexts.
* A.3 -- mandatory soft delete on domain models.
* Multitenancy -- tenant-scoped apps must not leak into the public schema.
"""

from django.apps import apps as django_apps
from django.conf import settings
from django.db import models

# Apps whose models carry business data and are therefore bound by rule A.3.
# ``users`` is absent from the cross-context checks below on purpose: identity is
# a local, same-schema concern that every context may reference directly.
DOMAIN_APP_LABELS = ("users", "academic", "billing", "tenants", "identity")

# Individual models exempt from the soft-delete rule, each with its reason.
# Keep this list short and justified -- it is the documented set of places where
# rule A.3 does not apply.
SOFT_DELETE_EXEMPT_MODELS: dict[str, str] = {
    "tenants.Domain": (
        "Routing configuration, not a business record. A hostname mapping must be "
        "genuinely removable: a soft-deleted row that still resolved would keep "
        "routing traffic to a decommissioned domain."
    ),
}


def _project_models(app_label: str) -> list[type[models.Model]]:
    return list(django_apps.get_app_config(app_label).get_models())


class TestNoCrossContextRelations:
    """Rule A.2: distant contexts communicate by UUID and services, not JOINs."""

    def test_billing_has_no_relation_into_academic(self) -> None:
        offenders = []
        for model in _project_models("billing"):
            for field in model._meta.get_fields():
                if not field.is_relation or field.related_model is None:
                    continue
                related_label = field.related_model._meta.app_label
                if related_label == "academic":
                    offenders.append(
                        f"{model._meta.label}.{field.name} -> " f"{field.related_model._meta.label}"
                    )
        assert not offenders, (
            "Billing must not hold ORM relations into the academic context. "
            "Reference it by UUID and read it through apps.academic.services. "
            f"Offending fields: {offenders}"
        )

    def test_academic_has_no_relation_into_billing(self) -> None:
        offenders = []
        for model in _project_models("academic"):
            for field in model._meta.get_fields():
                if not field.is_relation or field.related_model is None:
                    continue
                if field.related_model._meta.app_label == "billing":
                    offenders.append(
                        f"{model._meta.label}.{field.name} -> " f"{field.related_model._meta.label}"
                    )
        assert not offenders, (
            "The academic context must not depend on billing. " f"Offending fields: {offenders}"
        )

    def test_cross_context_references_are_uuid_typed(self) -> None:
        """The stand-ins for those FKs must be UUIDs, not integers or strings."""
        invoice = django_apps.get_model("billing", "Invoice")
        for field_name in ("enrollment_id", "student_id", "program_id"):
            field = invoice._meta.get_field(field_name)
            assert isinstance(field, models.UUIDField), (
                f"Invoice.{field_name} must be a UUIDField so the reference stays "
                "valid once the target context owns its own database."
            )


class TestSoftDeleteIsMandatory:
    """Rule A.3: domain records are deactivated, never physically deleted."""

    def test_domain_models_expose_soft_delete_fields(self) -> None:
        missing = []
        for app_label in DOMAIN_APP_LABELS:
            for model in _project_models(app_label):
                if model._meta.label in SOFT_DELETE_EXEMPT_MODELS:
                    continue
                field_names = {f.name for f in model._meta.get_fields()}
                if not {"is_active", "deleted_at"} <= field_names:
                    missing.append(model._meta.label)
        assert not missing, (
            "Every domain model needs is_active + deleted_at (inherit "
            f"apps.core.models.BaseModel). Missing on: {missing}"
        )

    def test_domain_models_override_delete(self) -> None:
        """``.delete()`` must not be Django's destructive implementation."""
        offenders = []
        for app_label in DOMAIN_APP_LABELS:
            for model in _project_models(app_label):
                if model._meta.label in SOFT_DELETE_EXEMPT_MODELS:
                    continue
                if model.delete is models.Model.delete:
                    offenders.append(model._meta.label)
        assert not offenders, f"These models still use Django's hard delete: {offenders}"

    def test_soft_delete_models_expose_an_escape_hatch(self) -> None:
        """A deliberate hard delete must remain possible for retention jobs."""
        for app_label in DOMAIN_APP_LABELS:
            for model in _project_models(app_label):
                if model._meta.label in SOFT_DELETE_EXEMPT_MODELS:
                    continue
                assert hasattr(model, "hard_delete") or hasattr(
                    model, "restore"
                ), f"{model._meta.label} should offer hard_delete()/restore()."

    def test_exemptions_are_documented_and_still_exist(self) -> None:
        """Stops the exemption list rotting into a silent blanket waiver."""
        for label, reason in SOFT_DELETE_EXEMPT_MODELS.items():
            app_label, model_name = label.split(".")
            assert (
                django_apps.get_model(app_label, model_name) is not None
            ), f"Exemption for {label} refers to a model that no longer exists."
            assert len(reason) > 40, f"Exemption for {label} needs a real reason."


class TestCrossSchoolIdentity:
    """Identity spans schools, so the boundary it crosses must stay a UUID."""

    def test_the_school_local_link_is_a_bare_uuid(self) -> None:
        """A ForeignKey here would point from a school's schema into public.

        Postgres would accept it -- ``public`` is on the search path -- and it
        would then be impossible to move a school's data to its own database,
        which is the entire reason rule A.2 exists.
        """
        user = django_apps.get_model("users", "User")
        field = user._meta.get_field("identity_id")
        assert isinstance(field, models.UUIDField), (
            "users.User.identity_id must be a plain UUIDField: it references a "
            "row in another schema, so it cannot be a ForeignKey."
        )
        assert not field.is_relation

    def test_no_tenant_app_holds_a_relation_into_identity(self) -> None:
        offenders = []
        for app_label in ("users", "academic", "billing"):
            for model in _project_models(app_label):
                for field in model._meta.get_fields():
                    if not field.is_relation or field.related_model is None:
                        continue
                    if field.related_model._meta.app_label == "identity":
                        offenders.append(f"{model._meta.label}.{field.name}")
        assert not offenders, (
            "Per-schema models must reference the platform identity by UUID, "
            f"never by ORM relation. Offending fields: {offenders}"
        )

    def test_identity_is_public_schema_only(self) -> None:
        assert "apps.identity" in settings.SHARED_APPS
        assert "apps.identity" not in settings.TENANT_APPS, (
            "Copying the membership table into every schema would let one "
            "school read which other schools employ a given person."
        )

    def test_the_schema_is_reset_around_every_request(self) -> None:
        """The single-domain model's load-bearing invariant.

        The hostname used to re-select the schema on every request, so a leak
        could not outlive one. Now the token selects it and something has to put
        it back -- if this middleware is dropped or demoted, a connection left
        pointing at a school serves the next caller that school's data.
        """
        middleware = settings.MIDDLEWARE
        resetter = "apps.tenants.middleware.PublicSchemaMiddleware"
        assert middleware[0] == resetter, (
            f"{resetter} must run first and therefore reset last; it is the only "
            "thing returning the connection to `public`."
        )
        assert "django_tenants.middleware.main.TenantMainMiddleware" not in middleware, (
            "Host-based tenant routing would fight the token-based selection: "
            "one domain cannot name a school."
        )


class TestTenantLayout:
    """The public schema must not carry school data, and vice versa."""

    def test_business_contexts_are_tenant_only(self) -> None:
        for app in ("apps.academic", "apps.billing", "apps.authentication"):
            assert app in settings.TENANT_APPS, f"{app} must be a TENANT_APP."
            assert app not in settings.SHARED_APPS, (
                f"{app} must NOT be in SHARED_APPS -- school data would land in "
                "the public schema, breaking isolation."
            )

    def test_tenant_registry_is_shared_only(self) -> None:
        assert "apps.tenants" in settings.SHARED_APPS
        assert "apps.tenants" not in settings.TENANT_APPS, (
            "The tenant registry belongs to the public schema only; copying it "
            "into every schema would let a school enumerate the others."
        )

    def test_identity_is_available_in_both_schemas(self) -> None:
        """Platform staff live in ``public``; school users live per-schema."""
        assert "apps.users" in settings.SHARED_APPS
        assert "apps.users" in settings.TENANT_APPS

    def test_every_model_owning_app_is_declared(self) -> None:
        """An app absent from both lists would never get its tables created."""
        declared = set(settings.SHARED_APPS) | set(settings.TENANT_APPS)
        undeclared = []
        for config in django_apps.get_app_configs():
            if not list(config.get_models()):
                continue
            if config.name not in declared:
                undeclared.append(config.name)
        assert not undeclared, (
            "These apps own models but appear in neither SHARED_APPS nor "
            f"TENANT_APPS, so migrate_schemas will skip them: {undeclared}"
        )


class TestTenantSecurityWiring:
    """The tenant claim check must stay wired into DRF's default auth."""

    def test_default_authentication_validates_the_tenant_claim(self) -> None:
        auth_classes = settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
        assert any("TenantJWTAuthentication" in path for path in auth_classes), (
            "DEFAULT_AUTHENTICATION_CLASSES must use TenantJWTAuthentication. "
            "Plain JWTAuthentication would accept a token issued by another "
            "institution."
        )

    def test_errors_go_through_the_shared_envelope(self) -> None:
        assert (
            settings.REST_FRAMEWORK["EXCEPTION_HANDLER"]
            == "apps.core.exceptions.api_exception_handler"
        )
