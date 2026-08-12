from django.urls import path

from .views import HealthCheckView

app_name = "core"

urlpatterns = [
    path("", HealthCheckView.as_view(), name="health"),
]
