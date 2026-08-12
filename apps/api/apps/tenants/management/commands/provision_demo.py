"""
Provision a demo school declaratively, from configuration alone.

Written for hosts where there is no shell: on free tiers you often cannot run a
one-off command, so anything that has to happen once must instead happen on
every boot without doing damage. This command is therefore **idempotent** — it
converges the tenant, its domain and its administrator towards the configured
state and is safe to run on every deploy.

Driven by environment variables so it needs no arguments:

    DEMO_SCHOOL_SCHEMA    e.g. demo
    DEMO_SCHOOL_NAME      e.g. "Demo School"
    DEMO_SCHOOL_SCHEMA    the school's Postgres schema; unset skips the whole
                          command, which is how a deployment opts out
    DEMO_CURRENCY         MXN or USD. Unset leaves the school's current value.
    DEMO_BRAND_COLOR      six-digit hex; the whole palette derives from it.
                          Unset leaves whatever the console configured.
    DEMO_ADMIN_EMAIL      administrator login
    DEMO_ADMIN_PASSWORD   optional; generated and printed once when absent
    DEMO_SEED             "true" to also load sample academic/billing data

With `DEMO_SCHOOL_SCHEMA` unset the command does nothing, so leaving it out of a
deployment is a supported choice rather than an error.
"""

import os
import secrets
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from apps.tenants.models import Client, Currency


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class Command(BaseCommand):
    help = "Idempotently provision a demo school from environment variables."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--schema", default=None)
        parser.add_argument("--name", default=None)
        parser.add_argument("--currency", default=None, choices=Currency.values)
        parser.add_argument("--brand-color", default=None)
        parser.add_argument("--admin-email", default=None)
        parser.add_argument("--admin-password", default=None)
        parser.add_argument("--seed", action="store_true", default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        schema = options["schema"] or _env("DEMO_SCHOOL_SCHEMA")
        name = options["name"] or _env("DEMO_SCHOOL_NAME", "Demo School")
        # Deliberately no default. These are reconciled on every boot, so a
        # default here would reset whatever an operator had configured in the
        # console the next time the service redeployed -- silently, and with
        # nothing in the interface to explain why the colour changed back.
        # Unset means "leave the institution as it is".
        currency = options["currency"] or _env("DEMO_CURRENCY") or None
        brand_color = options["brand_color"] or _env("DEMO_BRAND_COLOR") or None
        email = options["admin_email"] or _env("DEMO_ADMIN_EMAIL")
        password = options["admin_password"] or _env("DEMO_ADMIN_PASSWORD")
        seed = (
            options["seed"] if options["seed"] is not None else _env("DEMO_SEED").lower() == "true"
        )

        if not schema:
            self.stdout.write("DEMO_SCHOOL_SCHEMA not set — skipping provisioning.")
            return

        self._ensure_tenant(schema, name, currency, brand_color)

        if email:
            self._ensure_admin(schema, email, password)
        else:
            self.stdout.write("DEMO_ADMIN_EMAIL not set — no administrator created.")

        if seed:
            self._seed(schema)

        self.stdout.write(self.style.SUCCESS(f"Demo school '{schema}' ready."))

    # -- steps --------------------------------------------------------------
    def _ensure_tenant(
        self, schema: str, name: str, currency: str | None, brand_color: str | None
    ) -> Client:
        if currency is not None and currency not in Currency.values:
            raise CommandError(
                f"DEMO_CURRENCY must be one of {', '.join(Currency.values)}; got {currency!r}."
            )

        client = Client.objects.filter(schema_name=schema).first()
        if client is not None:
            # Applied on every boot, unlike the rest of the tenant: the currency
            # is the one setting an operator is likely to correct after the fact,
            # and a redeploy is the only lever a shell-less host offers.
            changed = []
            if currency is not None and client.default_currency != currency:
                client.default_currency = currency
                changed.append("default_currency")
            if brand_color is not None and client.brand_color != brand_color:
                client.brand_color = brand_color
                changed.append("brand_color")
            if changed:
                client.save(update_fields=[*changed, "updated_at"])
                self.stdout.write(f"Tenant '{schema}' updated: {', '.join(changed)}.")
            else:
                self.stdout.write(f"Tenant '{schema}' already exists.")
            return client

        # Saving triggers auto_create_schema, which runs the tenant migrations.
        # On creation only, an unset variable falls back to the model default.
        fields = {"schema_name": schema, "name": name}
        if currency is not None:
            fields["default_currency"] = currency
        if brand_color is not None:
            fields["brand_color"] = brand_color
        client = Client(**fields)
        client.save()
        self.stdout.write(self.style.SUCCESS(f"Created tenant '{schema}'."))
        return client

    def _ensure_admin(self, schema: str, email: str, password: str) -> None:
        """Create the administrator as a platform identity, not a schema row.

        A school-local user has no credential any more: the login form looks the
        address up platform-wide, because one hostname cannot say which school
        to search. Creating only the local row would produce an administrator
        who exists and cannot sign in -- which is precisely the failure this
        command exists to prevent on a host with no shell.
        """
        from apps.identity.models import Membership, PlatformIdentity
        from apps.identity.services import sync_user_from_identity

        generated = False
        normalised = email.strip().lower()

        identity = PlatformIdentity.all_objects.filter(email__iexact=normalised).first()
        if identity is not None:
            self.stdout.write(f"Administrator {email} already exists.")
            return

        if not password:
            password = secrets.token_urlsafe(12)
            generated = True

        client = Client.objects.get(schema_name=schema)
        identity = PlatformIdentity(
            email=normalised,
            first_name="School",
            last_name="Administrator",
            language=client.default_language,
        )
        identity.set_password(password)
        identity.save()
        membership = Membership.objects.create(
            identity=identity, tenant=client, role="school_admin"
        )

        with schema_context(schema):
            sync_user_from_identity(identity, membership)

        self.stdout.write(self.style.SUCCESS(f"Created administrator {email}."))
        if generated:
            # Printed once, to the deploy log -- the only channel available when
            # the platform offers no shell.
            self.stdout.write(self.style.WARNING(f"Generated password: {password}"))
            self.stdout.write("Nothing stores it. Copy it from this log now.")

    def _seed(self, schema: str) -> None:
        from django.core.management import call_command

        from apps.billing.models import Invoice

        with schema_context(schema):
            already_seeded = Invoice.all_objects.exists()

        if already_seeded:
            self.stdout.write("Sample data already present — not seeding again.")
            return

        self.stdout.write("Seeding sample data...")
        call_command("seed_demo", schema=schema)
