"""
URL configuration for biblioteca_digital project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.views.generic import RedirectView
from reports.views import admin_dashboard

urlpatterns = [
    path('', include('library_web.urls')),
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),
    path('api/', include('catalog.urls')),
    path('api/', include('circulation.urls')),
    path('api/', include('reports.urls')),
    path('legacy-dashboard/', admin_dashboard, name='legacy_admin_dashboard'),
    path('admin-dashboard/', RedirectView.as_view(url='/bibliotecario/', permanent=False), name='admin_dashboard'),
]
