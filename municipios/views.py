from django.http import JsonResponse
from django.db.models import Q
from .models import Cidade


def cidade_search(request):
    """API endpoint for Select2 city search."""
    term = request.GET.get("term", "").strip()
    page = int(request.GET.get("page", 1))
    per_page = 20

    queryset = Cidade.objects.all().order_by("nome", "uf")

    if term:
        queryset = queryset.filter(Q(nome__icontains=term) | Q(uf__iexact=term))

    # Pagination for Select2 infinite scroll
    start = (page - 1) * per_page
    end = start + per_page
    total = queryset.count()

    cidades = queryset[start:end]

    results = [
        {"id": cidade.pk, "text": f"{cidade.nome}/{cidade.uf}"} for cidade in cidades
    ]

    return JsonResponse({"results": results, "pagination": {"more": end < total}})
