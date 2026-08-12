"""
What a role outranks, and what it can reach.

These are two different questions and conflating them produces wrong answers, so
this module keeps them apart.

**Rank** is an administrative ladder. It answers "may this person act on that
one" -- assign them a role, edit them, deactivate them. Nobody may act on
somebody at or above their own rank, which is what stops an administrator
promoting themselves or editing a platform operator.

**Reach** is per module, and is *not* implied by rank. An accountant sits below
a coordinator on the ladder and yet is the one who issues invoices, while a
coordinator has no business in billing at all. A single ordering would have to
choose between letting coordinators into billing and locking accountants out;
both are wrong, so reach is declared per module in
:mod:`apps.core.modules` instead of derived from a number.
"""

from apps.users.models import UserRole

# Gaps are deliberate: a role can be slotted between two existing ones without
# renumbering every check that already ships.
ROLE_RANK: dict[str, int] = {
    UserRole.PLATFORM_ADMIN: 100,
    UserRole.SCHOOL_ADMIN: 80,
    UserRole.COORDINATOR: 60,
    UserRole.ACCOUNTANT: 50,
    UserRole.TEACHER: 40,
    UserRole.GUARDIAN: 20,
    UserRole.STUDENT: 10,
}

# An unknown role ranks below everything rather than above it. A typo in the
# database should cost someone access, never grant it.
UNKNOWN_RANK = 0


def rank_of(role: str | None) -> int:
    return ROLE_RANK.get(role or "", UNKNOWN_RANK)


def outranks(actor_role: str | None, target_role: str | None) -> bool:
    """May the actor act on someone holding ``target_role``?

    Strictly greater, so peers cannot act on each other: two school
    administrators can each manage their staff without being able to deactivate
    one another, and nobody can edit themselves into a higher role.
    """
    return rank_of(actor_role) > rank_of(target_role)


# The one role that may appoint its own equal. Everyone else is capped strictly
# below themselves, because granting a peer role is indistinguishable from
# self-promotion the moment the appointee returns the favour.
#
# The exception is not a softening. Someone already holding the highest
# authority gains nothing by escalation, and without it the platform could never
# acquire a second operator through the product at all -- the only way to mint
# one would be editing environment variables and redeploying, which is exactly
# the kind of out-of-band step that ends with a shared login.
TOP_ROLE = UserRole.PLATFORM_ADMIN


def assignable_roles(actor_role: str | None) -> list[str]:
    """The roles this person may hand out.

    Strictly below their own, so a school administrator can appoint coordinators
    and teachers but never another school administrator, and never a platform
    operator. See :data:`TOP_ROLE` for the single exception.
    """
    ceiling = rank_of(actor_role)
    allowed = [role for role, rank in ROLE_RANK.items() if rank < ceiling]
    if actor_role == TOP_ROLE:
        allowed.append(TOP_ROLE)
    return allowed
