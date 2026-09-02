"""
URL routing for the ``notifications`` app's API (CPMAS-22).

Mounted under /api/notifications/ by construction/urls.py.
"""
from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet

router = DefaultRouter()
router.register('notifications', NotificationViewSet, basename='notification')

urlpatterns = router.urls
