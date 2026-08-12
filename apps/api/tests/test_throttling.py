"""
Rate limiting on the credential endpoints.

Throttling is disabled in the test settings so it cannot interfere with the
fixtures (which log in constantly); each test here re-enables it explicitly and
clears the counter cache first, since counters are shared process state.
"""

from contextlib import contextmanager

import pytest
from django.core.cache import cache

from apps.authentication.throttling import (
    LoginEmailRateThrottle,
    LoginRateThrottle,
    RefreshRateThrottle,
)
from conftest import PASSWORD, TENANT_A

pytestmark = pytest.mark.django_db


@contextmanager
def throttled(login="3/min", refresh="3/min", login_email="100/min"):
    """Re-enable throttling at a low rate for the duration of a block.

    Patches the throttle classes rather than using ``override_settings``:
    DRF binds ``SimpleRateThrottle.THROTTLE_RATES`` as a **class attribute at
    import time**, so reloading ``api_settings`` leaves the classes pointing at
    the dict captured when the module was first imported. Overriding settings
    therefore appears to take effect one test late.

    Production is unaffected -- settings are final before DRF is imported -- so
    this is a test-only concern.
    """
    rates = {"login": login, "refresh": refresh, "login_email": login_email}
    originals = [
        (cls, cls.THROTTLE_RATES)
        for cls in (LoginRateThrottle, LoginEmailRateThrottle, RefreshRateThrottle)
    ]
    for cls, _ in originals:
        cls.THROTTLE_RATES = rates
    try:
        yield
    finally:
        for cls, original in originals:
            cls.THROTTLE_RATES = original


@pytest.fixture(autouse=True)
def _clear_throttle_counters():
    cache.clear()
    yield
    cache.clear()


class TestLoginThrottle:
    def test_repeated_failures_are_eventually_blocked(self, api_a, admin_a):
        """Credential stuffing must not get unlimited attempts."""
        with throttled():
            statuses = [
                api_a.post(
                    "/api/v1/auth/login/",
                    {"email": admin_a.email, "password": "wrong-password"},
                    format="json",
                ).status_code
                for _ in range(5)
            ]

        assert statuses[:3] == [401, 401, 401]
        assert 429 in statuses, statuses

    def test_the_envelope_is_used_for_429(self, api_a, admin_a):
        with throttled(login="1/min"):
            api_a.post(
                "/api/v1/auth/login/",
                {"email": admin_a.email, "password": "wrong"},
                format="json",
            )
            blocked = api_a.post(
                "/api/v1/auth/login/",
                {"email": admin_a.email, "password": "wrong"},
                format="json",
            )

        assert blocked.status_code == 429
        # Errors keep the project-wide shape even when DRF raises them.
        assert blocked.data["error"]["code"] == "throttled"
        assert "Retry-After" in blocked

    def test_successful_logins_also_count(self, api_a, admin_a):
        """The limit is on attempts, so a valid password cannot be used to probe."""
        with throttled(login="2/min"):
            first = api_a.post(
                "/api/v1/auth/login/",
                {"email": admin_a.email, "password": PASSWORD},
                format="json",
            )
            api_a.post(
                "/api/v1/auth/login/",
                {"email": admin_a.email, "password": PASSWORD},
                format="json",
            )
            third = api_a.post(
                "/api/v1/auth/login/",
                {"email": admin_a.email, "password": PASSWORD},
                format="json",
            )

        assert first.status_code == 200
        assert third.status_code == 429

    def test_the_address_budget_is_now_shared_between_schools(self, api_a, admin_a, admin_b):
        """A deliberate consequence of the single domain, pinned so it is noticed.

        The key used to include the schema, which the hostname supplied before
        the request body was read. There is no such hint any more -- finding out
        which school someone belongs to is the whole job of login -- so the
        address limit covers everyone behind that address, whatever school they
        work at. It is why this limit is generous and the per-account one is
        strict.
        """
        with throttled(login="2/min"):
            for _ in range(3):
                api_a.post(
                    "/api/v1/auth/login/",
                    {"email": admin_a.email, "password": "wrong"},
                    format="json",
                )

            # Another school's account, same address: also blocked.
            assert (
                api_a.post(
                    "/api/v1/auth/login/",
                    {"email": admin_b.email, "password": PASSWORD},
                    format="json",
                ).status_code
                == 429
            )


class TestRefreshThrottle:
    def test_refresh_is_limited(self, api_a, admin_a):
        # The refresh token now arrives as an httpOnly cookie, which the test
        # client stores and replays, so no body is needed.
        api_a.post(
            "/api/v1/auth/login/",
            {"email": admin_a.email, "password": PASSWORD},
            format="json",
        )

        with throttled(refresh="2/min"):
            statuses = [api_a.post("/api/v1/auth/refresh/").status_code for _ in range(4)]

        assert 429 in statuses, statuses

    def test_throttling_is_off_by_default_in_tests(self, api_a, admin_a):
        """Without this, the fixtures would exhaust the allowance."""
        statuses = [
            api_a.post(
                "/api/v1/auth/login/",
                {"email": admin_a.email, "password": "wrong"},
                format="json",
            ).status_code
            for _ in range(15)
        ]
        assert 429 not in statuses


class TestPerAccountThrottle:
    """The strict limit is per email, not per address."""

    def test_one_account_is_capped(self, api_a, admin_a):
        # Address limit wide open, account limit tight.
        with throttled(login="1000/min", login_email="2/min"):
            statuses = [
                api_a.post(
                    "/api/v1/auth/login/",
                    {"email": admin_a.email, "password": "wrong"},
                    format="json",
                ).status_code
                for _ in range(4)
            ]

        assert 429 in statuses, statuses

    def test_a_different_account_is_unaffected(self, api_a, admin_a, teacher_a):
        """Hammering one mailbox must not lock everyone else out."""
        with throttled(login="1000/min", login_email="2/min"):
            for _ in range(3):
                api_a.post(
                    "/api/v1/auth/login/",
                    {"email": admin_a.email, "password": "wrong"},
                    format="json",
                )

            assert (
                api_a.post(
                    "/api/v1/auth/login/",
                    {"email": admin_a.email, "password": "wrong"},
                    format="json",
                ).status_code
                == 429
            )

            # A colleague behind the same address can still sign in.
            assert (
                api_a.post(
                    "/api/v1/auth/login/",
                    {"email": teacher_a.email, "password": PASSWORD},
                    format="json",
                ).status_code
                == 200
            )

    def test_a_shared_address_is_not_the_tight_limit(self, api_a, tenant_a):
        """Many staff behind one NAT must not trip the per-account cap."""
        from conftest import _make_user

        for index in range(6):
            _make_user(
                TENANT_A["schema"],
                f"staff{index}@alpha.test",
                "teacher",
                last_name=str(index),
            )

        with throttled(login="1000/min", login_email="2/min"):
            statuses = [
                api_a.post(
                    "/api/v1/auth/login/",
                    {"email": f"staff{index}@alpha.test", "password": PASSWORD},
                    format="json",
                ).status_code
                for index in range(6)
            ]

        assert statuses == [200] * 6, statuses
