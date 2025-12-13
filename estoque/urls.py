from django.urls import path
from . import views

app_name = "estoque"

urlpatterns = [
    path("", views.EstoqueListView.as_view(), name="list"),
    path("<int:pk>/atualizar/", views.EstoqueUpdateView.as_view(), name="update"),
]
