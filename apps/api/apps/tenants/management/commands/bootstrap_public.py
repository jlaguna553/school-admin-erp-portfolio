"""
Create the ``public`` tenant and the platform superuser.

``django-tenants`` needs a ``Client`` row whose ``schema_name`` is ``public``
before any request can be served -- ``django-tenants`` resolves it through
the ``Domain`` table and 404s if nothing matches. This is the first command to
run on a fresh database, right after ``migrate_schemas --shared``.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.tenants.models import Client, Domain


class Command(BaseCommand):
    help = "Create the public tenant, its domain, and a platform superuser."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--domain", default="localhost")
        parser.add_argument("--name", default="Platform")
        parser.add_argument("--email", default=None, help="Platform superuser email.")
        parser.add_argument("--password", default=None)

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        domain_name: str = options["domain"]

        public, created = Client.objects.get_or_create(
            schema_name="public",
            defaults={"name": options["name"], "on_trial": False},
        )
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Found'} public tenant"))

        _domain, domain_created = Domain.objects.get_or_create(
            domain=domain_name,
            defaults={"tenant": public, "is_primary": True},
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if domain_created else 'Found'} domain '{domain_name}'")
        )

        email = options["email"]
        if not email:
            self.stdout.write(
                "No --email given; skipping superuser. "
                "Create one later with: manage.py createsuperuser"
            )
            return

        # Import here: the model is only resolvable once apps are loaded.
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        if user_model.all_objects.filter(email__iexact=email).exists():
            self.stdout.write(self.style.WARNING(f"User {email} already exists"))
            return

        password = options["password"]
        if not password:
            raise CommandError("--password is required when --email is given.")

        user_model.objects.create_superuser(
            email=email,
            password=password,
            first_name="Platform",
            last_name="Administrator",
        )
        self.stdout.write(self.style.SUCCESS(f"Created platform superuser {email}"))
