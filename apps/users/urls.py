"""
URL routing for the ``users`` app's Authentication & Authorization API.

Mounted under /api/auth/ (see ``construction/urls.py``). Auth action
endpoints (login/logout/me/password) are plain APIView routes; user
management is a DRF router mounted at ``users/``.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    RequestPasswordResetView,
    ResetPasswordView,
    TokenRefreshView,
    UserViewSet,
)

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')

urlpatterns = [
    path('login/', LoginView.as_view(), name='auth-login'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('change-password/', ChangePasswordView.as_view(), name='auth-change-password'),
    path('request-password-reset/', RequestPasswordResetView.as_view(), name='auth-request-password-reset'),
    path('reset-password/', ResetPasswordView.as_view(), name='auth-reset-password'),
] + router.urls
