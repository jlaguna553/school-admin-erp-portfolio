"""
Move every school-local credential into the platform identity table.

Under the host-per-school model an email only had to be unique *within* a
school, because the hostname disambiguated: `ana@example.com` at Northfield and
a different Ana at Riverside were two unrelated rows and both could sign in.

On a single domain that no longer works. The login form has nothing but the
email to go on, so the email has to identify one person platform-wide. This
command performs that consolidation, and refuses to guess where it cannot tell
two people apart.

Idempotent: users already linked to an identity are left alone, so it is safe to
run on every deploy.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from apps.identity.models import Membership, PlatformIdentity
from apps.tenants.models import Client
from apps.users.models import User, UserRole


class Command(BaseCommand):
    help = "Consolidate per-school user credentials into platform identities."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without writing anything.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        created = adopted = skipped = 0
        conflicts: list[str] = []

        for tenant in Client.objects.exclude(schema_name="public").order_by("name"):
            with schema_context(tenant.schema_name):
                users = list(User.all_objects.all())

            for user in users:
                outcome = self._migrate_one(tenant, user, dry_run, conflicts)
                if outcome == "created":
                    created += 1
                elif outcome == "adopted":
                    adopted += 1
                else:
                    skipped += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"identities created: {created} · existing reused: {adopted} · "
                f"already linked: {skipped}"
            )
        )

        if conflicts:
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR(
                    f"{len(conflicts)} account(s) could not be migrated because the "
                    "same email belongs to a different person at another school. "
                    "One domain means one person per email, so a human has to "
                    "decide: change one of the addresses, then run this again. "
                    "Until then those accounts cannot sign in."
                )
            )
            for line in conflicts:
                self.stdout.write(f"  - {line}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\ndry run: nothing was written"))

    # ------------------------------------------------------------------
    def _migrate_one(self, tenant: Client, user: User, dry_run: bool, conflicts: list[str]) -> str:
        if user.identity_id:
            return "skipped"

        email = user.email.strip().lower()
        identity = PlatformIdentity.all_objects.filter(email__iexact=email).first()

        if identity is not None and identity.password != user.password:
            # Same address, different password hash. Either the same person set
            # different passwords at two schools, or -- indistinguishably from
            # here -- they are two different people. Merging would hand one
            # person's account to the other, so neither is assumed.
            conflicts.append(f"{email} at {tenant.name} ({tenant.schema_name})")
            return "skipped"

        if dry_run:
            return "adopted" if identity else "created"

        with transaction.atomic():
            outcome = "adopted"
            if identity is None:
                identity = PlatformIdentity(
                    email=email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    phone=user.phone,
                    language=user.language,
                    # Copied, not re-hashed: nobody has to reset a password for
                    # this migration, and the raw value is not recoverable
                    # anyway.
                    password=user.password,
                    is_active=user.is_active,
                )
                identity.save()
                outcome = "created"

            role = user.role if user.role != UserRole.PLATFORM_ADMIN else UserRole.SCHOOL_ADMIN
            Membership.all_objects.update_or_create(
                identity=identity,
                tenant=tenant,
                defaults={
                    "role": role,
                    "is_active": user.is_active,
                    "deleted_at": None,
                },
            )

            with schema_context(tenant.schema_name):
                User.all_objects.filter(pk=user.pk).update(identity_id=identity.id)

        return outcome
