"""
The modules an institution runs, and who may reach each one.

This is the registry a modular monolith needs: one place saying what a module
is called, which roles read it, which roles write it, and whether an institution
may switch it off. Everything else -- the API permissions, the navigation the
frontend renders, the operator's toggles -- reads from here, so a module cannot
be reachable in one and invisible in the other.

Reach is declared per module rather than derived from :mod:`apps.core.roles`
ranks, because the ladder and the reach genuinely disagree: an accountant ranks
below a coordinator and is nonetheless the one who issues invoices.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.users.models import UserRole

# Roles that run the institution. Named once so the module table below reads as
# intent rather than as a repeated list.
ADMINISTRATION = (UserRole.SCHOOL_ADMIN, UserRole.COORDINATOR)
FINANCE = (UserRole.SCHOOL_ADMIN, UserRole.ACCOUNTANT)
TEACHING = (UserRole.SCHOOL_ADMIN, UserRole.COORDINATOR, UserRole.TEACHER)


class Module(models.TextChoices):
    """Every switchable area of the product."""

    USERS = "users", _("Users")
    ACADEMIC = "academic", _("Academic")
    SUBJECTS = "subjects", _("Subjects")
    GRADES = "grades", _("Gradebook")
    BILLING = "billing", _("Billing")
    SCHEDULE = "schedule", _("Schedule")
    ATTENDANCE = "attendance", _("Attendance")


class ModuleSpec:
    """One module's identity and access rules."""

    def __init__(
        self,
        key: str,
        *,
        read: tuple[str, ...],
        write: tuple[str, ...],
        optional: bool = True,
        requires: str | None = None,
    ) -> None:
        self.key = key
        self.read = read
        self.write = write
        # Whether an institution may switch it off. Users cannot be: a school
        # with no way to manage its people is a school nobody can administer.
        self.optional = optional
        # A module this one is useless without. Attendance is taken against a
        # timetabled class, so a school with the timetable switched off has
        # nothing to take a roll for -- and an operator who switched off one
        # module should not have to know that a second one silently broke.
        self.requires = requires


MODULES: dict[str, ModuleSpec] = {
    Module.USERS: ModuleSpec(
        Module.USERS,
        # Deliberately not "any authenticated user". A staff directory is
        # administrative: a student has no business enumerating their teachers'
        # contact details, and reading it was the default until roles were made
        # to mean something.
        read=ADMINISTRATION,
        write=(UserRole.SCHOOL_ADMIN,),
        optional=False,
    ),
    Module.ACADEMIC: ModuleSpec(
        Module.ACADEMIC,
        # Teachers read programmes and enrolments; they do not edit them.
        read=TEACHING,
        write=ADMINISTRATION,
    ),
    Module.SUBJECTS: ModuleSpec(
        Module.SUBJECTS,
        read=TEACHING,
        write=ADMINISTRATION,
    ),
    Module.GRADES: ModuleSpec(
        Module.GRADES,
        # The one module teachers *write*. Recording marks is their job, and the
        # object-level rule in `apps.academic.permissions` narrows it further to
        # the subjects they actually teach.
        read=TEACHING,
        write=TEACHING,
    ),
    Module.BILLING: ModuleSpec(
        Module.BILLING,
        # The one that shows why reach is not rank: an accountant sits below a
        # coordinator on the ladder, and a coordinator has no business here.
        read=FINANCE,
        write=FINANCE,
    ),
    Module.SCHEDULE: ModuleSpec(
        Module.SCHEDULE,
        read=TEACHING,
        write=ADMINISTRATION,
    ),
    Module.ATTENDANCE: ModuleSpec(
        Module.ATTENDANCE,
        # Written by teachers, like the gradebook and for the same reason: the
        # person in the room is the one who knows who is in it. Narrowed to
        # their own subjects by `apps.academic.permissions`.
        read=TEACHING,
        write=TEACHING,
        requires=Module.SCHEDULE,
    ),
}

OPTIONAL_MODULES: tuple[str, ...] = tuple(key for key, spec in MODULES.items() if spec.optional)


def enabled_modules(disabled: list[str] | None) -> list[str]:
    """The modules an institution actually runs.

    Institutions store what they have switched *off*, not what they have on. A
    module added in a later release is then live everywhere by default, instead
    of silently missing from every school provisioned before it existed --
    which is what an "enabled" list would do without a data migration on every
    release.
    """
    off = set(disabled or [])
    return [key for key in MODULES if is_enabled(key, disabled)] if off else list(MODULES)


def is_enabled(module: str, disabled: list[str] | None) -> bool:
    spec = MODULES.get(module)
    if spec is not None and not spec.optional:
        return True

    off = set(disabled or [])
    if module in off:
        return False

    # A module whose prerequisite is off is off too, and is reported that way
    # everywhere -- API, navigation, the operator's own list. The alternative is
    # a school where attendance appears in the menu, opens, and has nothing to
    # take a roll against because the timetable was switched off months ago.
    if spec is not None and spec.requires:
        return is_enabled(spec.requires, disabled)
    return True


def may_read(module: str, role: str | None) -> bool:
    spec = MODULES.get(module)
    return bool(spec and role in spec.read)


def may_write(module: str, role: str | None) -> bool:
    spec = MODULES.get(module)
    return bool(spec and role in spec.write)
