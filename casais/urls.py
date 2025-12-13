from django.urls import path
from . import views

app_name = "casais"

urlpatterns = [
    path("", views.CasalListView.as_view(), name="list"),
    path("buscar/", views.CasalBuscaView.as_view(), name="busca"),
    path("novo/", views.CasalCreateView.as_view(), name="create"),
    path("<int:pk>/", views.CasalDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.CasalUpdateView.as_view(), name="update"),
    path("<int:pk>/excluir/", views.CasalDeleteView.as_view(), name="delete"),
    # API para busca dinâmica
    path("api/buscar/", views.casal_search_api, name="api_search"),
]
