from django.urls import path
from . import views

app_name = "equipes"

urlpatterns = [
    path("", views.EquipeListView.as_view(), name="list"),
    path("novo/", views.EquipeCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.EquipeUpdateView.as_view(), name="update"),
    path("<int:pk>/excluir/", views.EquipeDeleteView.as_view(), name="delete"),
]
