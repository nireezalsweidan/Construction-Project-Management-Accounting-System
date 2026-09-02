from rest_framework.routers import DefaultRouter

from .views import EmployeeViewSet

# Registered on the empty prefix so the base endpoint is exactly
# /api/employees/ (no /employees/employees/ duplication) -- the app is
# mounted at ``path('api/employees/', ...)`` in construction/urls.py.
router = DefaultRouter()
router.register(r"", EmployeeViewSet, basename="employee")

urlpatterns = router.urls
