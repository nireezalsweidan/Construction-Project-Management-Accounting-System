"""
URL routing for the ``inventory`` app's Material Management API (CPMAS-28).

Mounted under /api/inventory/ by construction/urls.py. Uses a DRF
DefaultRouter so both viewsets get the standard list/create/retrieve/
update/destroy routes without hand-writing each path.
"""
from rest_framework.routers import DefaultRouter

from .views import MaterialCategoryViewSet, MaterialViewSet

router = DefaultRouter()
router.register('material-categories', MaterialCategoryViewSet, basename='materialcategory')
router.register('materials', MaterialViewSet, basename='material')

urlpatterns = router.urls
