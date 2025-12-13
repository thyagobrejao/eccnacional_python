from django.urls import path
from . import views

app_name = "materiais"

urlpatterns = [
    path("", views.MaterialListView.as_view(), name="list"),
    path("novo/", views.MaterialCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.MaterialUpdateView.as_view(), name="update"),
    path("<int:pk>/excluir/", views.MaterialDeleteView.as_view(), name="delete"),
    path("<int:pk>/preco/", views.SetMaterialPriceView.as_view(), name="set_price"),
]
