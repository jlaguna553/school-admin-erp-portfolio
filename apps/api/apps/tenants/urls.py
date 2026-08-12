from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ClientUserViewSet, ClientViewSet

app_name = "tenants"

router = DefaultRouter()
router.register("", ClientViewSet, basename="client")

client_users = ClientUserViewSet.as_view({"get": "list", "post": "create"})
client_user = ClientUserViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

# Declared before the router's routes: the router registers under an empty
# prefix, so its detail pattern sits at the same depth as these and order is
# the only thing keeping the intent unambiguous.
urlpatterns = [
    path("<uuid:client_pk>/users/", client_users, name="client-user-list"),
    path("<uuid:client_pk>/users/<uuid:pk>/", client_user, name="client-user-detail"),
    *router.urls,
]
