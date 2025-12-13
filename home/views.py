from django.views.generic import RedirectView
from django.urls import reverse_lazy


class HomeView(RedirectView):
    """View para a página inicial - redireciona para Pedidos Recebidos."""

    url = reverse_lazy("pedidos:recebidos")
