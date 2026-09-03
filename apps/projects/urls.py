from rest_framework.routers import DefaultRouter

from .views import BudgetItemViewSet, BudgetViewSet, ChangeOrderViewSet, PhaseViewSet, ProjectViewSet

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"phases", PhaseViewSet, basename="phase")
router.register(r"budgets", BudgetViewSet, basename="budget")
router.register(r"budget-items", BudgetItemViewSet, basename="budget-item")
router.register(r"change-orders", ChangeOrderViewSet, basename="change-order")

urlpatterns = router.urls