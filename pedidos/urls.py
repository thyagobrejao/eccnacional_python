from django.urls import path
from . import views

app_name = "pedidos"

urlpatterns = [
    path("novo/", views.PedidoCreateView.as_view(), name="novo"),
    path("recebidos/", views.PedidoRecebidosListView.as_view(), name="recebidos"),
    path("realizados/", views.PedidoRealizadosListView.as_view(), name="realizados"),
    path("busca/", views.PedidoSearchView.as_view(), name="busca"),
    path("<int:pk>/", views.PedidoDetailView.as_view(), name="detail"),
    path(
        "<int:pk>/status/", views.PedidoUpdateStatusView.as_view(), name="update_status"
    ),
    # APIs
    path("api/preco/", views.MaterialPriceAPIView.as_view(), name="api_preco"),
    path("api/materiais/", views.MaterialListAPIView.as_view(), name="api_materiais"),
]
