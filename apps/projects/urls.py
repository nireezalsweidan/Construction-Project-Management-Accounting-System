from rest_framework.routers import DefaultRouter

from .views import PhaseViewSet, ProjectViewSet

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"phases", PhaseViewSet, basename="phase")

urlpatterns = router.urls