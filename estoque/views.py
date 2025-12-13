from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from unidades.models import Unidade, UserUnidade
from materiais.models import Material, UnidadeMaterial


def get_valor_com_fallback(material_id, unidade, all_unidade_material_map):
    """
    Busca o valor do material para a unidade.
    Se não encontrar, sobe na hierarquia (parent) até encontrar ou chegar na Nacional.

    Args:
        material_id: ID do material
        unidade: Objeto Unidade inicial
        all_unidade_material_map: Dict {unidade_id: {material_id: UnidadeMaterial}}

    Returns:
        Tuple (valor, unidade_origem) - valor encontrado e unidade de onde veio
    """
    current = unidade
    visited = set()  # Evitar loops infinitos

    while current and current.id not in visited:
        visited.add(current.id)

        # Verificar se existe UnidadeMaterial para este material nesta unidade
        unidade_materiais = all_unidade_material_map.get(current.id, {})
        um = unidade_materiais.get(material_id)

        if um and um.valor is not None and um.valor > 0:
            return um.valor, current

        # Se é Nacional, para aqui (último nível)
        if current.tipo == Unidade.Tipo.NACIONAL:
            break

        # Subir para a unidade pai
        current = current.parent

    return None, None


class EstoqueListView(LoginRequiredMixin, ListView):
    """Lista materiais com estoque de todas as unidades do usuário."""

    template_name = "estoque/estoque_list.html"
    context_object_name = "estoque_items"

    def _get_unidades(self):
        """Obtém todas as unidades do usuário."""
        user = self.request.user

        if user.is_superuser:
            # Superuser vê todas as unidades
            return list(Unidade.objects.filter(status=True).order_by("nome"))

        # Usuário comum vê suas unidades ativas
        user_unidades = UserUnidade.objects.filter(
            user=user, status=True
        ).select_related("unidade")
        return [uu.unidade for uu in user_unidades]

    def _get_all_unidades_in_hierarchy(self, unidades):
        """
        Obtém todas as unidades na hierarquia (incluindo parents) para buscar valores.
        """
        all_ids = set()
        queue = list(unidades)

        while queue:
            u = queue.pop()
            if u and u.id not in all_ids:
                all_ids.add(u.id)
                if u.parent_id:
                    # Buscar parent se ainda não temos
                    queue.append(u.parent)

        return all_ids

    def get_queryset(self):
        self.unidades = self._get_unidades()

        if not self.unidades:
            return []

        # Buscar todas as unidades na hierarquia (incluindo parents)
        # para poder fazer o fallback de valor
        all_hierarchy_ids = self._get_all_unidades_in_hierarchy(self.unidades)

        # Buscar todos os materiais
        materiais = list(Material.objects.order_by("descricao"))

        # Buscar UnidadeMaterial de TODAS as unidades na hierarquia
        # para poder fazer fallback de valor
        all_um_qs = UnidadeMaterial.objects.filter(
            unidade_id__in=all_hierarchy_ids
        ).select_related("unidade", "material")

        # Mapa global: {unidade_id: {material_id: UnidadeMaterial}}
        all_unidade_material_map = {}
        for um in all_um_qs:
            if um.unidade_id not in all_unidade_material_map:
                all_unidade_material_map[um.unidade_id] = {}
            all_unidade_material_map[um.unidade_id][um.material_id] = um

        # Criar lista de itens: (unidade, material, estoque, valor, valor_origem)
        estoque_items = []
        for unidade in self.unidades:
            unidade_estoque = all_unidade_material_map.get(unidade.id, {})

            for material in materiais:
                um = unidade_estoque.get(material.id)
                quantidade = um.quantidade if um else 0

                # Buscar valor com fallback na hierarquia
                valor_proprio = um.valor if um else None
                if valor_proprio and valor_proprio > 0:
                    valor = valor_proprio
                    valor_origem = None  # Valor próprio, não precisa mostrar origem
                else:
                    valor, valor_origem_unidade = get_valor_com_fallback(
                        material.id, unidade.parent, all_unidade_material_map
                    )
                    valor_origem = valor_origem_unidade

                estoque_items.append(
                    {
                        "unidade": unidade,
                        "material": material,
                        "quantidade": quantidade,
                        "has_estoque": um is not None,
                        "valor": valor,
                        "valor_proprio": valor_proprio,
                        "valor_origem": valor_origem,  # Unidade de onde veio o valor (se fallback)
                    }
                )

        return estoque_items

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Estoque"
        context["unidades"] = getattr(self, "unidades", [])
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
