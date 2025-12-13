"""
URL configuration for eccnacional project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("blog.urls")),
    path("tinymce/", include("tinymce.urls")),
    path("gestao/", include("home.urls")),
    path("gestao/pedidos/", include("pedidos.urls")),
    path("gestao/municipios/", include("municipios.urls")),
    path("gestao/unidades/", include("unidades.urls")),
    path("gestao/materiais/", include("materiais.urls")),
    path("gestao/estoque/", include("estoque.urls")),
    path("gestao/equipes/", include("equipes.urls")),
    path("gestao/paroquias/", include("paroquias.urls")),
    path("gestao/encontros/", include("encontros.urls")),
    path("gestao/casais/", include("casais.urls")),
    # Authentication URLs
    path("gestao/login/", auth_views.LoginView.as_view(), name="login"),
    path("gestao/logout/", auth_views.LogoutView.as_view(), name="logout"),
]

# Servir arquivos de media durante o desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
