from django.urls import path
from . import views

app_name = "paroquias"

urlpatterns = [
    path("", views.ParoquiaListView.as_view(), name="list"),
    path("novo/", views.ParoquiaCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.ParoquiaUpdateView.as_view(), name="update"),
    path("<int:pk>/excluir/", views.ParoquiaDeleteView.as_view(), name="delete"),
]
