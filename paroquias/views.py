from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import HttpResponseForbidden
from unidades.models import Unidade, UserUnidade
from .models import Paroquia
from .forms import ParoquiaForm


class ParoquiaMixin:
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

    def can_edit(self, paroquia):
        """Verifica se o usuário pode editar a paróquia."""
        user = self.request.user
        if user.is_superuser:
            return True
        user_unidade_ids = self.get_user_unidade_ids()
        return paroquia.unidade_id in user_unidade_ids


class ParoquiaListView(LoginRequiredMixin, ParoquiaMixin, ListView):
    """Lista todas as paróquias (todos podem ver)."""

    model = Paroquia
    template_name = "paroquias/paroquia_list.html"
    context_object_name = "paroquias"
    ordering = ["nome"]

    def get_queryset(self):
        return Paroquia.objects.select_related("cidade", "unidade").order_by("nome")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Paróquias"
        context["user_unidade_ids"] = self.get_user_unidade_ids()
        return context


class ParoquiaCreateView(LoginRequiredMixin, ParoquiaMixin, CreateView):
    """Criar nova paróquia (todos podem criar)."""

    model = Paroquia
    form_class = ParoquiaForm
    template_name = "paroquias/paroquia_form.html"
    success_url = reverse_lazy("paroquias:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user_unidades"] = self.get_user_unidade_ids()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nova Paróquia"
        return context

    def form_valid(self, form):
        # A unidade já vem do formulário
        messages.success(self.request, "Paróquia criada com sucesso!")
        return super().form_valid(form)


class ParoquiaUpdateView(LoginRequiredMixin, ParoquiaMixin, UpdateView):
    """Editar paróquia (apenas da própria unidade)."""

    model = Paroquia
    form_class = ParoquiaForm
    template_name = "paroquias/paroquia_form.html"
    success_url = reverse_lazy("paroquias:list")

    def dispatch(self, request, *args, **kwargs):
        paroquia = self.get_object()
        if not self.can_edit(paroquia):
            return HttpResponseForbidden(
                "Você só pode editar paróquias da sua unidade."
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
        messages.success(self.request, "Paróquia atualizada com sucesso!")
        return super().form_valid(form)


class ParoquiaDeleteView(LoginRequiredMixin, ParoquiaMixin, DeleteView):
    """Excluir paróquia (apenas da própria unidade)."""

    model = Paroquia
    success_url = reverse_lazy("paroquias:list")

    def dispatch(self, request, *args, **kwargs):
        paroquia = self.get_object()
        if not self.can_edit(paroquia):
            return HttpResponseForbidden(
                "Você só pode excluir paróquias da sua unidade."
            )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        messages.success(request, "Paróquia excluída com sucesso!")
        return super().post(request, *args, **kwargs)
