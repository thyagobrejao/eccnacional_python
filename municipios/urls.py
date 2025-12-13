from django.urls import path
from . import views

app_name = "municipios"

urlpatterns = [
    path("api/cidades/", views.cidade_search, name="cidade_search"),
]
