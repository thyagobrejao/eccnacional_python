from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
    DetailView,
    View,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseForbidden
from django.db.models import Q
from unidades.models import Unidade, UserUnidade
from .models import Encontro, CasalEncontro
from .forms import EncontroForm, CasalEncontroForm, EncontroBuscaForm


class EncontroMixin:
    """Mixin para obter unidades do usuário."""

    def get_user_unidade_ids(self):
        """Obtém IDs das unidades do usuário."""
        user = self.request.user
        if user.is_superuser:
            return list(Unidade.objects.values_list("id", flat=True))
        return list(
            UserUnidade.objects.filter(user=user, status=True).values_list(
                "unidade_id", flat=True
            )
        )

    def get_user_unidade(self):
        """Obtém a primeira unidade do usuário."""
        user = self.request.user
        if user.is_superuser:
            return Unidade.objects.filter(tipo=Unidade.Tipo.NACIONAL).first()
        user_unidade = (
            UserUnidade.objects.filter(user=user, status=True)
            .select_related("unidade")
            .first()
        )
        return user_unidade.unidade if user_unidade else None

    def can_edit(self, encontro):
        """Verifica se o usuário pode editar o encontro."""
        user = self.request.user
        if user.is_superuser:
            return True
        user_unidade_ids = self.get_user_unidade_ids()
        return encontro.unidade_id in user_unidade_ids


class EncontroListView(LoginRequiredMixin, EncontroMixin, ListView):
    """Lista todos os encontros (todos podem ver)."""

    model = Encontro
    template_name = "encontros/encontro_list.html"
    context_object_name = "encontros"
    ordering = ["-data"]
    paginate_by = 20

    def get_queryset(self):
        return Encontro.objects.select_related("unidade", "paroquia").order_by("-data")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Encontros"
        context["user_unidade_ids"] = self.get_user_unidade_ids()
        return context


class EncontroDetailView(LoginRequiredMixin, EncontroMixin, DetailView):
    """Detalhes do encontro com lista de casais."""

    model = Encontro
    template_name = "encontros/encontro_detail.html"
    context_object_name = "encontro"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Encontro: {self.object.nome}"
        context["can_edit"] = self.can_edit(self.object)
        context["casais_encontro"] = CasalEncontro.objects.filter(
            encontro=self.object
        ).select_related("casal", "equipe")
        context["form_add_casal"] = CasalEncontroForm(encontro=self.object)
        return context


class EncontroCreateView(LoginRequiredMixin, EncontroMixin, CreateView):
    """Criar novo encontro."""

    model = Encontro
    form_class = EncontroForm
    template_name = "encontros/encontro_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user_unidades"] = self.get_user_unidade_ids()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Novo Encontro"
        return context

    def form_valid(self, form):
        # A unidade já vem do formulário
        messages.success(self.request, "Encontro criado com sucesso!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("encontros:detail", kwargs={"pk": self.object.pk})


class EncontroUpdateView(LoginRequiredMixin, EncontroMixin, UpdateView):
    """Editar encontro (apenas da própria unidade)."""

    model = Encontro
    form_class = EncontroForm
    template_name = "encontros/encontro_form.html"

    def dispatch(self, request, *args, **kwargs):
        encontro = self.get_object()
        if not self.can_edit(encontro):
            return HttpResponseForbidden(
                "Você só pode editar encontros da sua unidade."
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user_unidades"] = self.get_user_unidade_ids()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Editar: {self.object.nome}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Encontro atualizado com sucesso!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("encontros:detail", kwargs={"pk": self.object.pk})


class EncontroDeleteView(LoginRequiredMixin, EncontroMixin, DeleteView):
    """Excluir encontro (apenas da própria unidade)."""

    model = Encontro
    success_url = reverse_lazy("encontros:list")

    def dispatch(self, request, *args, **kwargs):
        encontro = self.get_object()
        if not self.can_edit(encontro):
            return HttpResponseForbidden(
                "Você só pode excluir encontros da sua unidade."
            )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        messages.success(request, "Encontro excluído com sucesso!")
        return super().post(request, *args, **kwargs)


class EncontroBuscaView(LoginRequiredMixin, EncontroMixin, ListView):
    """Busca de encontros."""

    model = Encontro
    template_name = "encontros/encontro_busca.html"
    context_object_name = "encontros"
    paginate_by = 20

    def get_queryset(self):
        queryset = Encontro.objects.select_related("unidade", "paroquia").order_by(
            "-data"
        )

        q = self.request.GET.get("q", "").strip()
        data_inicio = self.request.GET.get("data_inicio")
        data_fim = self.request.GET.get("data_fim")

        if q:
            queryset = queryset.filter(
                Q(nome__icontains=q) | Q(paroquia__nome__icontains=q)
            )
        if data_inicio:
            queryset = queryset.filter(data__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data__lte=data_fim)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Buscar Encontros"
        context["form"] = EncontroBuscaForm(self.request.GET)
        context["user_unidade_ids"] = self.get_user_unidade_ids()
        return context


class EncontroAddCasalView(LoginRequiredMixin, EncontroMixin, View):
    """Adicionar casal ao encontro."""

    def post(self, request, pk):
        encontro = get_object_or_404(Encontro, pk=pk)

        if not self.can_edit(encontro):
            return HttpResponseForbidden(
                "Você só pode adicionar casais a encontros da sua unidade."
            )

        form = CasalEncontroForm(request.POST, encontro=encontro)

        if form.is_valid():
            casal_encontro = form.save(commit=False)
            casal_encontro.encontro = encontro
            casal_encontro.save()
            messages.success(request, "Casal adicionado ao encontro!")
        else:
            messages.error(request, "Erro ao adicionar casal.")

        return redirect("encontros:detail", pk=pk)


class EncontroRemoveCasalView(LoginRequiredMixin, EncontroMixin, View):
    """Remover casal do encontro."""

    def post(self, request, pk, casal_pk):
        encontro = get_object_or_404(Encontro, pk=pk)

        if not self.can_edit(encontro):
            return HttpResponseForbidden(
                "Você só pode remover casais de encontros da sua unidade."
            )

        CasalEncontro.objects.filter(encontro=encontro, casal_id=casal_pk).delete()
        messages.success(request, "Casal removido do encontro!")

        return redirect("encontros:detail", pk=pk)
