"""
Provision a school: its Postgres schema, its hostname, and its first admin.

Creating the ``Client`` row triggers ``auto_create_schema``, which runs the whole
``TENANT_APPS`` migration set inside the new schema. The school admin is then
created *within* that schema via ``schema_context``, so the row lands in the
school's own ``users_user`` table and is invisible to every other tenant.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import schema_context

from apps.tenants.models import Client, Domain


class Command(BaseCommand):
    help = "Provision a new school (schema + domain + first administrator)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--schema", required=True, help="e.g. northfield")
        parser.add_argument("--name", required=True, help='e.g. "Northfield School"')
        parser.add_argument(
            "--domain",
            default=None,
            help="Defaults to <schema>.localhost for local development.",
        )
        parser.add_argument("--language", default="es", choices=["es", "en"])
        parser.add_argument("--admin-email", default=None)
        parser.add_argument("--admin-password", default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        schema: str = options["schema"].strip().lower()
        if schema == "public":
            raise CommandError("'public' is reserved for the platform tenant.")
        if Client.objects.filter(schema_name=schema).exists():
            raise CommandError(f"A tenant with schema '{schema}' already exists.")

        domain_name: str = options["domain"] or f"{schema}.localhost"

        # Not wrapped in a single atomic block: schema creation issues DDL that
        # django-tenants manages itself.
        client = Client.objects.create(
            schema_name=schema,
            name=options["name"],
            default_language=options["language"],
            on_trial=True,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Created schema '{schema}' and ran tenant migrations")
        )

        with transaction.atomic():
            Domain.objects.get_or_create(
                domain=domain_name,
                defaults={"tenant": client, "is_primary": True},
            )
        self.stdout.write(self.style.SUCCESS(f"Mapped domain '{domain_name}'"))

        email = options["admin_email"]
        password = options["admin_password"]
        if not email:
            self.stdout.write("No --admin-email given; skipping school admin.")
            return
        if not password:
            raise CommandError("--admin-password is required with --admin-email.")

        from django.contrib.auth import get_user_model

        user_model = get_user_model()

        # Switch into the school's schema so the user row is created there.
        with schema_context(schema):
            if user_model.all_objects.filter(email__iexact=email).exists():
                self.stdout.write(self.style.WARNING(f"{email} already exists in '{schema}'"))
                return
            user_model.objects.create_user(
                email=email,
                password=password,
                first_name="School",
                last_name="Administrator",
                role="school_admin",
                language=options["language"],
                is_staff=True,
            )
        self.stdout.write(self.style.SUCCESS(f"Created school administrator {email} in '{schema}'"))
        self.stdout.write("")
        self.stdout.write(f"  API:   http://{domain_name}:8000/api/health/")
        self.stdout.write(f"  Admin: http://{domain_name}:8000/admin/")
