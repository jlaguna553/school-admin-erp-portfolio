from django.urls import path

from apps.identity.views import AvailableSchoolsView

from .views import LoginView, LogoutView, RefreshView, SwitchSchoolView, VerifyView

app_name = "authentication"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("verify/", VerifyView.as_view(), name="verify"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # Empty unless the caller signs in with a platform-wide credential.
    path("schools/", AvailableSchoolsView.as_view(), name="schools"),
    # Moves the session to another of the caller's schools, without a
    # second sign-in.
    path("switch/", SwitchSchoolView.as_view(), name="switch"),
]
