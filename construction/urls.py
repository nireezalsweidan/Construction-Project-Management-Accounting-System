"""
URL configuration for construction project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),

    # Each domain app mounts its own DRF router under /api/<app>/ as it's
    # built out, so this list grows one line per app rather than
    # centralizing all routes here.
    path('api/inventory/', include('inventory.urls')),  # CPMAS-28, CPMAS-29
    path('api/purchasing/', include('purchasing.urls')),  # CPMAS-30
]
