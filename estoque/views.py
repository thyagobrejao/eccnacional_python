from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from unidades.models import Unidade, UserUnidade
from materiais.models import Material, UnidadeMaterial


class EstoqueListView(LoginRequiredMixin, ListView):
    """Lista materiais com estoque da unidade selecionada."""

    template_name = "estoque/estoque_list.html"
    context_object_name = "estoque_items"

    def _get_user_unidades(self):
        """Obtém todas as unidades do usuário."""
        user = self.request.user
        if user.is_superuser:
            return list(Unidade.objects.filter(status=True).order_by("nome"))
        user_unidades = UserUnidade.objects.filter(
            user=user, status=True
        ).select_related("unidade")
        return [uu.unidade for uu in user_unidades]

    def _get_selected_unidade(self, unidades):
        """Obtém a unidade selecionada via GET param ou a primeira da lista."""
        unidade_id = self.request.GET.get("unidade")
        if unidade_id:
            try:
                uid = int(unidade_id)
                for u in unidades:
                    if u.id == uid:
                        return u
            except (ValueError, TypeError):
                pass
        return unidades[0] if unidades else None

    def _build_valor_fallback(self, material_id, start_unidade, all_um_map, all_unidades_dict):
        """
        Busca o valor do material subindo na hierarquia usando dict em memória.
        Evita queries N+1 de acesso a .parent.
        """
        current = start_unidade
        visited = set()
        while current and current.id not in visited:
            visited.add(current.id)
            um = all_um_map.get(current.id, {}).get(material_id)
            if um and um.valor is not None and um.valor > 0:
                return um.valor, current
            if current.tipo == Unidade.Tipo.NACIONAL:
                break
            current = all_unidades_dict.get(current.parent_id) if current.parent_id else None
        return None, None

    def get_queryset(self):
        self.unidades = self._get_user_unidades()
        if not self.unidades:
            self.selected_unidade = None
            return []

        self.selected_unidade = self._get_selected_unidade(self.unidades)
        if not self.selected_unidade:
            return []

        # Carrega TODAS as unidades em memória de uma só vez para evitar N+1
        all_unidades_dict = {u.id: u for u in Unidade.objects.only("id", "parent_id", "tipo", "nome")}

        # Atualiza referência para usar o objeto com parent_id correto
        self.selected_unidade = all_unidades_dict.get(self.selected_unidade.id, self.selected_unidade)

        # Coleta IDs da hierarquia ancestral para fallback de valor
        hierarchy_ids = set()
        current = self.selected_unidade
        visited = set()
        while current and current.id not in visited:
            visited.add(current.id)
            hierarchy_ids.add(current.id)
            if current.tipo == Unidade.Tipo.NACIONAL:
                break
            current = all_unidades_dict.get(current.parent_id) if current.parent_id else None

        # Uma única query para materiais e uma para UnidadeMaterial da hierarquia
        materiais = list(Material.objects.order_by("descricao"))
        all_um_qs = UnidadeMaterial.objects.filter(unidade_id__in=hierarchy_ids)

        all_um_map = {}
        for um in all_um_qs:
            all_um_map.setdefault(um.unidade_id, {})[um.material_id] = um

        unidade_estoque = all_um_map.get(self.selected_unidade.id, {})
        parent_unidade = all_unidades_dict.get(self.selected_unidade.parent_id) if self.selected_unidade.parent_id else None

        estoque_items = []
        for material in materiais:
            um = unidade_estoque.get(material.id)
            quantidade = um.quantidade if um else 0
            valor_proprio = um.valor if um else None

            if valor_proprio and valor_proprio > 0:
                valor = valor_proprio
                valor_origem = None
            else:
                valor, valor_origem = self._build_valor_fallback(
                    material.id, parent_unidade, all_um_map, all_unidades_dict
                )

            estoque_items.append({
                "unidade": self.selected_unidade,
                "material": material,
                "quantidade": quantidade,
                "has_estoque": um is not None,
                "valor": valor,
                "valor_proprio": valor_proprio,
                "valor_origem": valor_origem,
            })

        return estoque_items

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Estoque"
        context["unidades"] = getattr(self, "unidades", [])
        context["selected_unidade"] = getattr(self, "selected_unidade", None)
        context["multiple_unidades"] = len(getattr(self, "unidades", [])) > 1
        return context


class EstoqueUpdateView(LoginRequiredMixin, View):
    """Atualiza a quantidade em estoque de um material para uma unidade."""

    def _get_user_unidades(self, user):
        """Obtém IDs das unidades do usuário."""
        if user.is_superuser:
            return list(Unidade.objects.values_list("id", flat=True))

        return list(
            UserUnidade.objects.filter(user=user, status=True).values_list(
                "unidade_id", flat=True
            )
        )

    def post(self, request, pk):
        material = get_object_or_404(Material, pk=pk)

        # Obter unidade do request (pode vir do formulário)
        unidade_id = request.POST.get("unidade_id")
        if not unidade_id:
            error = "Unidade não especificada."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error}, status=400)
            messages.error(request, error)
            return redirect("estoque:list")

        try:
            unidade_id = int(unidade_id)
        except (ValueError, TypeError):
            error = "Unidade inválida."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error}, status=400)
            messages.error(request, error)
            return redirect("estoque:list")

        # Verificar se o usuário tem acesso a essa unidade
        user_unidade_ids = self._get_user_unidades(request.user)
        if unidade_id not in user_unidade_ids:
            error = "Você não tem permissão para alterar o estoque desta unidade."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error}, status=403)
            return HttpResponseForbidden(error)

        unidade = get_object_or_404(Unidade, pk=unidade_id)

        try:
            quantidade = int(request.POST.get("quantidade", 0))
            if quantidade < 0:
                raise ValueError("Quantidade não pode ser negativa")
        except (ValueError, TypeError):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "error": "Quantidade inválida"}, status=400
                )
            messages.error(request, "Quantidade inválida")
            return redirect("estoque:list")

        # Criar ou atualizar UnidadeMaterial
        unidade_material, _ = UnidadeMaterial.objects.get_or_create(
            unidade=unidade, material=material, defaults={"valor": 0, "quantidade": 0}
        )
        unidade_material.quantidade = quantidade
        unidade_material.save()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": True,
                    "message": f'Estoque de "{material.descricao}" atualizado!',
                    "quantidade": quantidade,
                }
            )

        messages.success(request, f'Estoque de "{material.descricao}" atualizado!')
        return redirect("estoque:list")
