from rest_framework.routers import DefaultRouter

from .views import ContractorViewSet

# Registered on the empty prefix so the base endpoint is exactly
# /api/contractors/ (no /contractors/contractors/ duplication) -- the app is
# mounted at ``path('api/contractors/', ...)`` in construction/urls.py.
router = DefaultRouter()
router.register(r"", ContractorViewSet, basename="contractor")

urlpatterns = router.urls