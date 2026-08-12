"""
Per-school branding, after the move to a single domain.

A school's colour used to be servable to an anonymous visitor, because the
hostname said which school was being visited. One domain removes that: the login
page belongs to the platform, and a school's palette can only be applied once
the session says which school it is. The colour therefore travels in the login
response and in the access token, not in an unauthenticated lookup.

What stays true is that the colour is a per-school setting, validated as a
six-digit hex, and that the whole palette derives from it.
"""

import pytest

from conftest import PASSWORD, tenant_setting

pytestmark = pytest.mark.django_db


class TestPlatformBranding:
    def test_the_unauthenticated_endpoint_serves_the_platform(self, api_a, tenants):
        """No school is knowable before signing in, so none is guessed."""
        response = api_a.get("/api/v1/branding/")

        assert response.status_code == 200
        assert response.data["schema"] == "public"

    def test_it_is_readable_without_signing_in(self, api_a, tenants):
        assert api_a.get("/api/v1/branding/").status_code == 200


class TestSchoolColourReachesTheClient:
    def test_the_login_response_carries_the_school_colour(self, api_a, admin_a):
        response = api_a.post(
            "/api/v1/auth/login/",
            {"email": admin_a.email, "password": PASSWORD},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["tenant"]["brand_color"] == "#1d4ed8"

    def test_the_colour_travels_in_the_access_token(self, api_a, admin_a):
        """So a reload can repaint before any request returns."""
        from rest_framework_simplejwt.tokens import AccessToken

        response = api_a.post(
            "/api/v1/auth/login/",
            {"email": admin_a.email, "password": PASSWORD},
            format="json",
        )
        claims = AccessToken(response.data["access"])

        assert claims["brand_color"] == "#1d4ed8"

    def test_each_school_reports_its_own(self, api_a, admin_a):
        with tenant_setting("test_alpha", brand_color="#0f766e"):
            response = api_a.post(
                "/api/v1/auth/login/",
                {"email": admin_a.email, "password": PASSWORD},
                format="json",
            )
        assert response.data["tenant"]["brand_color"] == "#0f766e"


class TestColourValidation:
    def test_a_non_hex_colour_is_refused(self, as_platform, tenant_a):
        response = as_platform.patch(
            f"/api/v1/tenants/{tenant_a.id}/",
            {"brand_color": "cornflower blue"},
            format="json",
        )

        assert response.status_code == 400
        assert "brand_color" in response.data["error"]["details"]

    def test_a_three_digit_hex_is_refused(self, as_platform, tenant_a):
        """The frontend's derivation parses six digits only."""
        response = as_platform.patch(
            f"/api/v1/tenants/{tenant_a.id}/", {"brand_color": "#abc"}, format="json"
        )

        assert response.status_code == 400

    def test_an_operator_can_set_it(self, as_platform, tenant_a, api_a, admin_a):
        response = as_platform.patch(
            f"/api/v1/tenants/{tenant_a.id}/", {"brand_color": "#7c3aed"}, format="json"
        )
        try:
            assert response.status_code == 200, response.data
            # Visible to that school's staff on their next sign-in.
            login = api_a.post(
                "/api/v1/auth/login/",
                {"email": admin_a.email, "password": PASSWORD},
                format="json",
            )
            assert login.data["tenant"]["brand_color"] == "#7c3aed"
        finally:
            as_platform.patch(
                f"/api/v1/tenants/{tenant_a.id}/", {"brand_color": "#1d4ed8"}, format="json"
            )
