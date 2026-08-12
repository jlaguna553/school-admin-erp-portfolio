from rest_framework.routers import DefaultRouter

from .views import PlatformIdentityViewSet

app_name = "identity"

router = DefaultRouter()
router.register("", PlatformIdentityViewSet, basename="identity")

urlpatterns = router.urls
