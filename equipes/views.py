from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import HttpResponseForbidden
from unidades.models import Unidade, UserUnidade
from .models import Equipe
from .forms import EquipeForm


class IsNacionalMixin:
    """Mixin para verificar se usuário é Nacional ou superuser."""

    def is_nacional(self):
        user = self.request.user
        if user.is_superuser:
            return True

        return UserUnidade.objects.filter(
            user=user, status=True, unidade__tipo=Unidade.Tipo.NACIONAL
        ).exists()


class EquipeListView(LoginRequiredMixin, IsNacionalMixin, ListView):
    """Lista todas as equipes."""

    model = Equipe
    template_name = "equipes/equipe_list.html"
    context_object_name = "equipes"
    ordering = ["nome"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Equipes"
        context["is_nacional"] = self.is_nacional()
        return context


class EquipeCreateView(LoginRequiredMixin, IsNacionalMixin, CreateView):
    """Criar nova equipe (apenas Nacional)."""

    model = Equipe
    form_class = EquipeForm
    template_name = "equipes/equipe_form.html"
    success_url = reverse_lazy("equipes:list")

    def dispatch(self, request, *args, **kwargs):
        if not self.is_nacional():
            return HttpResponseForbidden(
                "Apenas usuários Nacional podem criar equipes."
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nova Equipe"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Equipe criada com sucesso!")
        return super().form_valid(form)


class EquipeUpdateView(LoginRequiredMixin, IsNacionalMixin, UpdateView):
    """Editar equipe (apenas Nacional)."""

    model = Equipe
    form_class = EquipeForm
    template_name = "equipes/equipe_form.html"
    success_url = reverse_lazy("equipes:list")

    def dispatch(self, request, *args, **kwargs):
        if not self.is_nacional():
            return HttpResponseForbidden(
                "Apenas usuários Nacional podem editar equipes."
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Editar: {self.object.nome}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Equipe atualizada com sucesso!")
        return super().form_valid(form)


class EquipeDeleteView(LoginRequiredMixin, IsNacionalMixin, DeleteView):
    """Excluir equipe (apenas Nacional)."""

    model = Equipe
    success_url = reverse_lazy("equipes:list")

    def dispatch(self, request, *args, **kwargs):
        if not self.is_nacional():
            return HttpResponseForbidden(
                "Apenas usuários Nacional podem excluir equipes."
            )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        messages.success(request, "Equipe excluída com sucesso!")
        return super().post(request, *args, **kwargs)
