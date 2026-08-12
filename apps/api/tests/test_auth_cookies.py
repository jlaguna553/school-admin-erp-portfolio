"""
Refresh-token delivery.

The security property under test is narrow but important: JavaScript must not be
able to read the refresh token, while a browser must still be able to spend it.
"""

import pytest
from django.conf import settings as configured

from conftest import PASSWORD

pytestmark = pytest.mark.django_db

# Aliased on import so the name `settings` is free for pytest-django's fixture.
COOKIE = configured.AUTH_COOKIE_NAME


def login(api, user):
    return api.post(
        "/api/v1/auth/login/",
        {"email": user.email, "password": PASSWORD},
        format="json",
    )


class TestLoginSetsTheCookie:
    def test_access_is_returned_but_refresh_is_not(self, api_a, admin_a):
        response = login(api_a, admin_a)

        assert response.status_code == 200
        assert "access" in response.data
        # Returning it in the body as well would defeat the httpOnly cookie.
        assert "refresh" not in response.data

    def test_the_cookie_is_httponly_and_scoped(self, api_a, admin_a):
        response = login(api_a, admin_a)
        cookie = response.cookies[COOKIE]

        assert cookie.value
        # The whole point: unreachable from document.cookie.
        assert cookie["httponly"] is True
        assert cookie["samesite"] == "Lax"
        # Not attached to ordinary API calls, only the auth endpoints.
        assert cookie["path"] == "/api/v1/auth/"
        assert int(cookie["max-age"]) > 0

    def test_secure_follows_configuration(self, api_a, admin_a, settings):
        """Off over plain http in development, forced on in production."""
        settings.AUTH_COOKIE_SECURE = True
        response = login(api_a, admin_a)
        assert response.cookies[COOKIE]["secure"] is True

    def test_body_delivery_can_be_enabled_for_native_clients(self, api_a, admin_a, settings):
        settings.AUTH_REFRESH_IN_BODY = True
        response = login(api_a, admin_a)
        assert "refresh" in response.data


class TestRefreshUsesTheCookie:
    def test_refresh_works_with_no_request_body(self, api_a, admin_a):
        login(api_a, admin_a)

        response = api_a.post("/api/v1/auth/refresh/")

        assert response.status_code == 200, response.data
        assert "access" in response.data
        assert "refresh" not in response.data

    def test_rotation_issues_a_new_cookie(self, api_a, admin_a):
        original = login(api_a, admin_a).cookies[COOKIE].value

        response = api_a.post("/api/v1/auth/refresh/")

        assert response.status_code == 200
        assert response.cookies[COOKIE].value != original

    def test_the_rotated_token_cannot_be_reused(self, api_a, admin_a):
        """Rotation plus blacklisting means a stolen token has one use."""
        stolen = login(api_a, admin_a).cookies[COOKIE].value
        api_a.post("/api/v1/auth/refresh/")  # rotates and blacklists `stolen`

        replay = api_a.post("/api/v1/auth/refresh/", {"refresh": stolen}, format="json")

        assert replay.status_code == 401

    def test_no_token_at_all_is_rejected(self, api_a):
        assert api_a.post("/api/v1/auth/refresh/").status_code == 401

    def test_a_garbage_cookie_is_rejected(self, api_a):
        api_a.cookies[COOKIE] = "not-a-jwt"
        assert api_a.post("/api/v1/auth/refresh/").status_code == 401

    def test_an_explicit_body_still_wins(self, api_a, admin_a):
        """Native clients keep working without cookies."""
        token = login(api_a, admin_a).cookies[COOKIE].value
        api_a.cookies.clear()

        response = api_a.post("/api/v1/auth/refresh/", {"refresh": token}, format="json")
        assert response.status_code == 200

    def test_a_refreshed_access_token_is_usable(self, api_a, admin_a):
        login(api_a, admin_a)
        access = api_a.post("/api/v1/auth/refresh/").data["access"]

        api_a.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me = api_a.get("/api/v1/users/me/")

        assert me.status_code == 200
        assert me.data["email"] == admin_a.email


class TestLogoutClearsTheCookie:
    def test_logout_expires_the_cookie_and_blacklists_the_token(self, api_a, admin_a):
        access = login(api_a, admin_a).data["access"]
        token = api_a.cookies[COOKIE].value
        api_a.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = api_a.post("/api/v1/auth/logout/")
        assert response.status_code == 204
        # An expired cookie with an empty value is how a cookie is deleted.
        assert response.cookies[COOKIE].value == ""

        api_a.credentials()
        api_a.cookies.clear()
        replay = api_a.post("/api/v1/auth/refresh/", {"refresh": token}, format="json")
        assert replay.status_code == 401

    def test_logout_requires_authentication(self, api_a):
        assert api_a.post("/api/v1/auth/logout/").status_code == 401
