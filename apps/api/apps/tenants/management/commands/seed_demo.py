"""
Populate a school's schema with believable demo data.

Useful for development and for demonstrating the dashboard, but it earns its
place for another reason: it drives the billing context through
``apps.billing.services``, which is the only sanctioned path across the
academic/billing boundary. If someone breaks that boundary, this command stops
working.

    python manage.py seed_demo --schema northfield
"""

import random
import secrets
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from apps.tenants.models import Client

FIRST_NAMES = [
    "Lucía",
    "Mateo",
    "Sofía",
    "Hugo",
    "Martina",
    "Daniel",
    "Valeria",
    "Pablo",
    "Emma",
    "Álvaro",
    "Carla",
    "Diego",
    "Noa",
    "Adrián",
    "Jimena",
    "Bruno",
]
LAST_NAMES = [
    "García",
    "Rodríguez",
    "Fernández",
    "López",
    "Martínez",
    "Sánchez",
    "Pérez",
    "Gómez",
    "Ruiz",
    "Díaz",
    "Moreno",
    "Álvarez",
]

PROGRAMS = [
    ("PRI", "Educación Primaria", "Primary Education"),
    ("SEC", "Educación Secundaria", "Secondary Education"),
    ("BAC", "Bachillerato", "High School"),
]

SUBJECTS = [
    ("MAT", "Matemáticas", "Mathematics", 6),
    ("LEN", "Lengua y Literatura", "Language and Literature", 5),
    ("CIE", "Ciencias Naturales", "Natural Sciences", 4),
    ("HIS", "Historia", "History", 3),
    ("ING", "Inglés", "English", 4),
]


class Command(BaseCommand):
    help = "Seed a tenant schema with demo academic and billing data."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--schema", required=True)
        parser.add_argument("--students", type=int, default=48)
        parser.add_argument("--teachers", type=int, default=7)
        parser.add_argument("--seed", type=int, default=20260726, help="RNG seed.")
        parser.add_argument(
            "--password",
            default=None,
            help=(
                "Password for every seeded account. Defaults to a freshly "
                "generated one, printed once. Pass an explicit value only if "
                "visitors are meant to sign in as a demo student."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        schema: str = options["schema"]
        if not Client.objects.filter(schema_name=schema).exists():
            raise CommandError(
                f"No tenant with schema '{schema}'. Create it with create_school first."
            )

        random.seed(options["seed"])

        # Seeded accounts are real, working logins. Hard-coding one meant that
        # anybody reading this repository could sign in to a deployed demo as
        # student1@example.test and page through the whole roster -- so the
        # default is now generated per run, and sharing it is a deliberate act.
        password: str = options["password"] or secrets.token_urlsafe(12)
        generated = options["password"] is None

        # Everything below runs inside the school's own schema.
        with schema_context(schema):
            self._seed(options["students"], options["teachers"], password)

        self.stdout.write("")
        if generated:
            self.stdout.write(
                self.style.WARNING(f"Generated password for all seeded accounts: {password}")
            )
            self.stdout.write("Not stored anywhere -- note it now if you need it.")
        else:
            self.stdout.write("Seeded accounts use the password you supplied.")

    def _seed(self, student_count: int, teacher_count: int, password: str) -> None:
        from django.contrib.auth import get_user_model

        from apps.academic.models import (
            AcademicYear,
            Enrollment,
            EnrollmentStatus,
            Program,
            StudentGroup,
            Subject,
            TimetableSlot,
        )
        from apps.billing import services as billing_services

        user_model = get_user_model()

        # --- Academic year -------------------------------------------------
        today = date.today()
        start_year = today.year if today.month >= 9 else today.year - 1
        year, _ = AcademicYear.objects.get_or_create(
            name=f"{start_year}-{start_year + 1}",
            defaults={
                "start_date": date(start_year, 9, 1),
                "end_date": date(start_year + 1, 6, 30),
                "is_current": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Academic year: {year.name}"))

        # --- Programmes (translated fields written per language) -----------
        programs: list[Program] = []
        for code, name_es, name_en in PROGRAMS:
            program, created = Program.objects.get_or_create(
                code=code,
                defaults={"name_es": name_es, "name_en": name_en},
            )
            if not created:
                program.name_es = name_es
                program.name_en = name_en
                program.save(update_fields=["name_es", "name_en", "updated_at"])
            programs.append(program)
        self.stdout.write(self.style.SUCCESS(f"Programmes: {len(programs)}"))

        # --- Teachers ------------------------------------------------------
        teachers = []
        for index in range(teacher_count):
            email = f"teacher{index + 1}@example.test"
            teacher = user_model.all_objects.filter(email=email).first()
            if teacher is None:
                teacher = user_model.objects.create_user(
                    email=email,
                    password=password,
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    role="teacher",
                )
            teachers.append(teacher)
        self.stdout.write(self.style.SUCCESS(f"Teachers: {len(teachers)}"))

        # --- Subjects ------------------------------------------------------
        subject_total = 0
        for program in programs:
            for code, name_es, name_en, credits in SUBJECTS:
                _, created = Subject.objects.get_or_create(
                    program=program,
                    code=code,
                    defaults={
                        "name_es": name_es,
                        "name_en": name_en,
                        "credits": credits,
                        "teacher": random.choice(teachers),
                    },
                )
                subject_total += 1 if created else 0
        self.stdout.write(self.style.SUCCESS(f"Subjects created: {subject_total}"))

        # --- Groups ---------------------------------------------------------
        # One section per programme. Without them the timetable and the register
        # are both reachable and neither is usable, which is the state a freshly
        # seeded school would otherwise ship in.
        groups: dict[Any, StudentGroup] = {}
        for position, program in enumerate(programs):
            group, _ = StudentGroup.objects.get_or_create(
                program=program,
                academic_year=year,
                name="A",
                defaults={
                    "tutor": teachers[position % len(teachers)] if teachers else None,
                    "room": f"Aula {position + 1}",
                },
            )
            groups[program.id] = group
        self.stdout.write(self.style.SUCCESS(f"Groups: {len(groups)}"))

        # --- Students & enrollments ----------------------------------------
        enrollments: list[Enrollment] = []
        for index in range(student_count):
            email = f"student{index + 1}@example.test"
            student = user_model.all_objects.filter(email=email).first()
            if student is None:
                student = user_model.objects.create_user(
                    email=email,
                    password=password,
                    first_name=random.choice(FIRST_NAMES),
                    last_name=random.choice(LAST_NAMES),
                    role="student",
                )

            program = programs[index % len(programs)]
            enrollment, _ = Enrollment.objects.get_or_create(
                student=student,
                program=program,
                academic_year=year,
                defaults={
                    "status": EnrollmentStatus.ACTIVE,
                    "enrolled_on": year.start_date,
                    "group": groups.get(program.id),
                },
            )
            if enrollment.group_id is None:
                # A school seeded before groups existed: put its students in one
                # rather than leaving every register empty.
                enrollment.group = groups.get(program.id)
                enrollment.save(update_fields=["group", "updated_at"])
            enrollments.append(enrollment)
        self.stdout.write(self.style.SUCCESS(f"Students/enrollments: {len(enrollments)}"))

        # --- Timetable ------------------------------------------------------
        # Monday to Friday, one subject an hour from 08:00, placed through the
        # same clash detector the API uses. Writing the rows straight to the ORM
        # would be shorter and would happily double-book a teacher across two
        # programmes -- the seed shares its teachers -- leaving a demo school
        # that cannot be edited without first untangling it.
        from apps.academic import timetable as timetable_service

        slots_created = 0
        for group in groups.values():
            subjects = list(Subject.objects.filter(program=group.program).order_by("code"))
            for position, subject in enumerate(subjects[:10]):
                weekday = position % 5 + 1
                if TimetableSlot.objects.filter(group=group, subject=subject).exists():
                    continue

                for hour in range(8, 15):
                    start, end = time(hour, 0), time(hour + 1, 0)
                    if timetable_service.find_clashes(
                        group=group,
                        subject=subject,
                        weekday=weekday,
                        start=start,
                        end=end,
                        room=group.room,
                    ):
                        continue
                    TimetableSlot.objects.create(
                        group=group,
                        subject=subject,
                        weekday=weekday,
                        start_time=start,
                        end_time=end,
                        room=group.room,
                    )
                    slots_created += 1
                    break
        self.stdout.write(self.style.SUCCESS(f"Timetable entries created: {slots_created}"))

        # --- Invoices, strictly through the billing service ---------------
        # No ORM join is available here by design: the service resolves the
        # enrollment via apps.academic.services and snapshots its labels.
        from apps.billing.models import Invoice

        created_invoices = 0
        overdue = 0
        if Invoice.all_objects.count() == 0:
            for position, enrollment in enumerate(enrollments[:24]):
                # Make a third of them already past due so the KPI is non-zero.
                is_late = position % 3 == 0
                issue = today - timedelta(days=60 if is_late else 5)
                due = issue + timedelta(days=30)

                invoice = billing_services.create_invoice_for_enrollment(
                    enrollment_id=enrollment.id,
                    lines=[
                        {"description": "Matrícula anual", "unit_price": Decimal("450.00")},
                        {"description": "Material escolar", "unit_price": Decimal("75.50")},
                    ],
                    issue_date=issue,
                    due_date=due,
                    currency="EUR",
                )
                created_invoices += 1

                if is_late:
                    billing_services.recalculate_invoice_status(invoice)
                    invoice.refresh_from_db()
                    if invoice.status == "overdue":
                        overdue += 1
                else:
                    # Settle a few in full so statuses vary.
                    if position % 4 == 1:
                        billing_services.register_payment(
                            invoice=invoice,
                            amount=invoice.subtotal,
                            method="transfer",
                            received_on=issue + timedelta(days=3),
                        )

        self.stdout.write(self.style.SUCCESS(f"Invoices: {created_invoices} (overdue: {overdue})"))
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo data ready."))
