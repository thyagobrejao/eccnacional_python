from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.http import HttpResponseForbidden
from unidades.models import Unidade, UserUnidade
from .models import Material, UnidadeMaterial
from .forms import MaterialForm, UnidadeMaterialForm


class IsNacionalMixin:
    """Mixin para verificar se usuário é de unidade Nacional."""

    def is_nacional(self):
        user = self.request.user
        if user.is_superuser:
            return True

        return UserUnidade.objects.filter(
            user=user, status=True, unidade__tipo=Unidade.Tipo.NACIONAL
        ).exists()


def get_valor_com_fallback(material_id, unidade, all_unidade_material_map):
    """
    Busca o valor do material para a unidade.
    Se não encontrar, sobe na hierarquia (parent) até encontrar ou chegar na Nacional.
    """
    current = unidade
    visited = set()

    while current and current.id not in visited:
        visited.add(current.id)

        unidade_materiais = all_unidade_material_map.get(current.id, {})
        um = unidade_materiais.get(material_id)

        if um and um.valor is not None and um.valor > 0:
            return um.valor, current

        if current.tipo == Unidade.Tipo.NACIONAL:
            break

        current = current.parent

    return None, None


class MaterialListView(LoginRequiredMixin, IsNacionalMixin, ListView):
    """Lista todos os materiais."""

    model = Material
    template_name = "materiais/material_list.html"
    context_object_name = "materiais"
    ordering = ["descricao"]

    def _get_unidade_do_usuario(self):
        """Obtém a unidade principal do usuário."""
        user = self.request.user

        if user.is_superuser:
            return Unidade.objects.filter(tipo=Unidade.Tipo.NACIONAL).first()

        user_unidade = (
            UserUnidade.objects.filter(user=user, status=True)
            .select_related("unidade")
            .first()
        )
        return user_unidade.unidade if user_unidade else None

    def _get_user_unidades(self):
        """Obtém todas as unidades do usuário."""
        user = self.request.user
        if user.is_superuser:
            return Unidade.objects.all()
        return Unidade.objects.filter(
            id__in=UserUnidade.objects.filter(user=user, status=True).values_list(
                "unidade_id", flat=True
            )
        )

    def _get_unidade_selecionada(self):
        """Obtém a unidade selecionada via query parameter ou a primeira do usuário."""
        unidade_id = self.request.GET.get("unidade")
        user_unidades = self._get_user_unidades()

        if unidade_id:
            try:
                return user_unidades.get(id=int(unidade_id))
            except (ValueError, Unidade.DoesNotExist):
                pass

        return user_unidades.first()

    def _get_all_hierarchy_ids(self, unidade):
        """Obtém IDs de todas as unidades na hierarquia (até Nacional)."""
        ids = set()
        current = unidade
        while current and current.id not in ids:
            ids.add(current.id)
            if current.tipo == Unidade.Tipo.NACIONAL:
                break
            current = current.parent
        return ids

    def get_queryset(self):
        queryset = super().get_queryset()

        # Determinar unidade selecionada
        self.unidade_usuario = self._get_unidade_selecionada()

        if not self.unidade_usuario:
            # Sem unidade, retorna materiais sem preço
            materiais = list(queryset)
            for material in materiais:
                material.preco = None
                material.valor_efetivo = None
                material.valor_origem = None
            return materiais

        # Buscar todas as unidades na hierarquia para fallback
        hierarchy_ids = self._get_all_hierarchy_ids(self.unidade_usuario)

        # Buscar UnidadeMaterial de todas as unidades na hierarquia
        all_um_qs = UnidadeMaterial.objects.filter(
            unidade_id__in=hierarchy_ids
        ).select_related("unidade", "material")

        # Mapa: {unidade_id: {material_id: UnidadeMaterial}}
        all_unidade_material_map = {}
        for um in all_um_qs:
            if um.unidade_id not in all_unidade_material_map:
                all_unidade_material_map[um.unidade_id] = {}
            all_unidade_material_map[um.unidade_id][um.material_id] = um

        # Anexar preço com fallback a cada material
        materiais = list(queryset)
        unidade_materiais = all_unidade_material_map.get(self.unidade_usuario.id, {})

        for material in materiais:
            um = unidade_materiais.get(material.pk)
            material.preco = um  # UnidadeMaterial próprio (pode ser None)

            # Verificar se tem valor próprio
            valor_proprio = um.valor if um else None
            if valor_proprio and valor_proprio > 0:
                material.valor_efetivo = valor_proprio
                material.valor_origem = None
            else:
                # Buscar valor com fallback (começando do parent)
                valor, origem = get_valor_com_fallback(
                    material.pk, self.unidade_usuario.parent, all_unidade_material_map
                )
                material.valor_efetivo = valor
                material.valor_origem = origem  # Unidade de onde veio o valor

        return materiais

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Materiais"
        context["is_nacional"] = self.is_nacional()
        context["user_unidades"] = list(self._get_user_unidades().values("id", "nome"))
        context["unidade_selecionada"] = self.unidade_usuario
        return context


class MaterialCreateView(LoginRequiredMixin, IsNacionalMixin, CreateView):
    """Criar novo material (apenas Nacional)."""

    model = Material
    form_class = MaterialForm
    template_name = "materiais/material_form.html"
    success_url = reverse_lazy("materiais:list")

    def dispatch(self, request, *args, **kwargs):
        if not self.is_nacional():
            return HttpResponseForbidden(
                "Apenas usuários Nacional podem criar materiais."
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Novo Material"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Material criado com sucesso!")
        return super().form_valid(form)


class MaterialUpdateView(LoginRequiredMixin, IsNacionalMixin, UpdateView):
    """Editar material (apenas Nacional)."""

    model = Material
    form_class = MaterialForm
    template_name = "materiais/material_form.html"
    success_url = reverse_lazy("materiais:list")

    def dispatch(self, request, *args, **kwargs):
        if not self.is_nacional():
            return HttpResponseForbidden(
                "Apenas usuários Nacional podem editar materiais."
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Editar: {self.object.descricao}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Material atualizado com sucesso!")
        return super().form_valid(form)


class MaterialDeleteView(LoginRequiredMixin, IsNacionalMixin, DeleteView):
    """Excluir material (apenas Nacional)."""

    model = Material
    success_url = reverse_lazy("materiais:list")

    def dispatch(self, request, *args, **kwargs):
        if not self.is_nacional():
            return HttpResponseForbidden(
                "Apenas usuários Nacional podem excluir materiais."
            )
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        messages.success(request, "Material excluído com sucesso!")
        return super().post(request, *args, **kwargs)


class SetMaterialPriceView(LoginRequiredMixin, View):
    """Definir preço do material para a unidade do usuário."""

    def _get_user_unidades(self, user):
        """Obtém todas as unidades do usuário."""
        if user.is_superuser:
            return Unidade.objects.all()
        return Unidade.objects.filter(
            id__in=UserUnidade.objects.filter(user=user, status=True).values_list(
                "unidade_id", flat=True
            )
        )

    def _get_unidade(self, user, unidade_id=None):
        """Obtém a unidade selecionada ou a primeira do usuário."""
        user_unidades = self._get_user_unidades(user)

        # Se unidade_id foi fornecida, tentar usar
        if unidade_id:
            try:
                return user_unidades.get(id=int(unidade_id)), None
            except (ValueError, Unidade.DoesNotExist):
                pass

        # Caso contrário, pegar a primeira unidade
        unidade = user_unidades.first()
        if not unidade:
            return None, "Você não está vinculado a nenhuma unidade."

        return unidade, None

    def get(self, request, pk):
        material = get_object_or_404(Material, pk=pk)

        unidade_id = request.GET.get("unidade")
        unidade, error = self._get_unidade(request.user, unidade_id)
        if error:
            return HttpResponseForbidden(error)

        # Buscar ou criar UnidadeMaterial
        unidade_material, _ = UnidadeMaterial.objects.get_or_create(
            unidade=unidade, material=material, defaults={"valor": 0, "quantidade": 0}
        )

        form = UnidadeMaterialForm(instance=unidade_material)
        return self._render(request, material, unidade, form)

    def post(self, request, pk):
        material = get_object_or_404(Material, pk=pk)

        unidade_id = request.POST.get("unidade_id") or request.GET.get("unidade")
        unidade, error = self._get_unidade(request.user, unidade_id)
        if error:
            return HttpResponseForbidden(error)

        unidade_material, _ = UnidadeMaterial.objects.get_or_create(
            unidade=unidade, material=material, defaults={"valor": 0, "quantidade": 0}
        )

        form = UnidadeMaterialForm(request.POST, instance=unidade_material)

        if form.is_valid():
            form.save()
            messages.success(request, f'Preço de "{material.descricao}" atualizado!')
            return redirect("materiais:list")

        return self._render(request, material, unidade, form)

    def _render(self, request, material, unidade, form):
        from django.shortcuts import render

        user_unidades = self._get_user_unidades(request.user)

        return render(
            request,
            "materiais/set_price.html",
            {
                "page_title": f"Definir Preço: {material.descricao}",
                "material": material,
                "unidade": unidade,
                "form": form,
                "user_unidades": list(user_unidades.values("id", "nome")),
            },
        )
