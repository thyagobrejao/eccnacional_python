from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
    DetailView,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q
from .models import Casal
from .forms import CasalForm
from encontros.models import CasalEncontro


class CasalDetailView(LoginRequiredMixin, DetailView):
    """Detalhes do casal com histórico de encontros e equipes."""

    model = Casal
    template_name = "casais/casal_detail.html"
    context_object_name = "casal"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"{self.object}"

        # Buscar todos os encontros do casal com suas equipes
        casal_encontros = (
            CasalEncontro.objects.filter(casal=self.object)
            .select_related(
                "encontro", "encontro__unidade", "encontro__paroquia", "equipe"
            )
            .order_by("-encontro__data")
        )

        context["casal_encontros"] = casal_encontros

        # Listar equipes únicas
        equipes = set()
        for ce in casal_encontros:
            if ce.equipe:
                equipes.add(ce.equipe)
        context["equipes"] = sorted(equipes, key=lambda e: e.nome)

        return context


class CasalListView(LoginRequiredMixin, ListView):
    """Lista todos os casais."""

    model = Casal
    template_name = "casais/casal_list.html"
    context_object_name = "casais"
    ordering = ["ele", "ela"]
    paginate_by = 20

    def get_queryset(self):
        return Casal.objects.select_related("paroquia").order_by("ele", "ela")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Casais"
        return context


class CasalCreateView(LoginRequiredMixin, CreateView):
    """Criar novo casal."""

    model = Casal
    form_class = CasalForm
    template_name = "casais/casal_form.html"
    success_url = reverse_lazy("casais:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Novo Casal"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Casal cadastrado com sucesso!")
        return super().form_valid(form)


class CasalUpdateView(LoginRequiredMixin, UpdateView):
    """Editar casal."""

    model = Casal
    form_class = CasalForm
    template_name = "casais/casal_form.html"
    success_url = reverse_lazy("casais:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Editar: {self.object}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Casal atualizado com sucesso!")
        return super().form_valid(form)


class CasalDeleteView(LoginRequiredMixin, DeleteView):
    """Excluir casal."""

    model = Casal
    success_url = reverse_lazy("casais:list")

    def post(self, request, *args, **kwargs):
        messages.success(request, "Casal excluído com sucesso!")
        return super().post(request, *args, **kwargs)


class CasalBuscaView(LoginRequiredMixin, ListView):
    """Busca de casais com filtros."""

    model = Casal
    template_name = "casais/casal_busca.html"
    context_object_name = "casais"
    paginate_by = 20

    def get_queryset(self):
        queryset = Casal.objects.select_related("paroquia").order_by("ele", "ela")

        # Aplicar filtros
        q = self.request.GET.get("q", "").strip()
        email = self.request.GET.get("email", "").strip()
        telefone = self.request.GET.get("telefone", "").strip()
        paroquia_id = self.request.GET.get("paroquia", "").strip()

        if q:
            queryset = queryset.filter(Q(ele__icontains=q) | Q(ela__icontains=q))

        if email:
            queryset = queryset.filter(
                Q(email_ele__icontains=email) | Q(email_ela__icontains=email)
            )

        if telefone:
            # Remover caracteres especiais para busca
            telefone_clean = (
                telefone.replace("(", "")
                .replace(")", "")
                .replace("-", "")
                .replace(" ", "")
            )
            queryset = queryset.filter(
                Q(telefone_ele__icontains=telefone_clean)
                | Q(telefone_ela__icontains=telefone_clean)
            )

        if paroquia_id:
            try:
                queryset = queryset.filter(paroquia_id=int(paroquia_id))
            except ValueError:
                pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Buscar Casais"

        from .forms import CasalBuscaForm

        # Preencher form com valores da busca
        context["form"] = CasalBuscaForm(self.request.GET or None)

        return context


def casal_search_api(request):
    """API para busca dinâmica de casais por e-mail ou telefone."""
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 3:
        return JsonResponse({"casais": []})

    # Buscar por e-mail ou telefone
    casais = Casal.objects.filter(
        Q(email_ele__icontains=query)
        | Q(email_ela__icontains=query)
        | Q(telefone_ele__icontains=query)
        | Q(telefone_ela__icontains=query)
    ).select_related("paroquia")[:10]

    results = []
    for casal in casais:
        results.append(
            {
                "id": casal.id,
                "ele": casal.ele,
                "ela": casal.ela,
                "email_ele": casal.email_ele or "",
                "email_ela": casal.email_ela or "",
                "telefone_ele": casal.telefone_ele or "",
                "telefone_ela": casal.telefone_ela or "",
                "paroquia": casal.paroquia.nome if casal.paroquia else "",
                "display": f"{casal.ele} e {casal.ela}",
            }
        )

    return JsonResponse({"casais": results})
