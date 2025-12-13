from django.urls import path
from . import views

app_name = "encontros"

urlpatterns = [
    path("", views.EncontroListView.as_view(), name="list"),
    path("novo/", views.EncontroCreateView.as_view(), name="create"),
    path("busca/", views.EncontroBuscaView.as_view(), name="busca"),
    path("<int:pk>/", views.EncontroDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.EncontroUpdateView.as_view(), name="update"),
    path("<int:pk>/excluir/", views.EncontroDeleteView.as_view(), name="delete"),
    # Gerenciamento de casais
    path(
        "<int:pk>/casais/adicionar/",
        views.EncontroAddCasalView.as_view(),
        name="add_casal",
    ),
    path(
        "<int:pk>/casais/<int:casal_pk>/remover/",
        views.EncontroRemoveCasalView.as_view(),
        name="remove_casal",
    ),
]
