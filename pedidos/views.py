from django.views.generic import CreateView, ListView, DetailView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from .models import Pedido, PedidoMaterial
from .forms import PedidoForm, PedidoMaterialFormSet, PedidoSearchForm
from unidades.models import Unidade, UserUnidade
from materiais.models import Material, UnidadeMaterial


def get_material_price_for_unidade(material_id, unidade):
    """
    Busca o preço do material subindo na hierarquia de unidades.
    Começa na unidade pai e sobe até encontrar um preço ou chegar na Nacional.
    """
    current = unidade.parent if unidade.parent else unidade

    while current:
        try:
            um = UnidadeMaterial.objects.get(material_id=material_id, unidade=current)
            return {
                "preco": float(um.valor),
                "unidade_origem": current.nome,
                "unidade_tipo": current.get_tipo_display(),
            }
        except UnidadeMaterial.DoesNotExist:
            current = current.parent

    return {"preco": 0, "unidade_origem": None, "unidade_tipo": None}


class MaterialPriceAPIView(LoginRequiredMixin, View):
    """API para buscar preço de material com base na hierarquia de unidades."""

    def get(self, request):
        material_id = request.GET.get("material_id")
        unidade_id = request.GET.get("unidade_id")

        if not material_id or not unidade_id:
            return JsonResponse(
                {"error": "material_id e unidade_id são obrigatórios"}, status=400
            )

        try:
            unidade = Unidade.objects.get(pk=unidade_id)
        except Unidade.DoesNotExist:
            return JsonResponse({"error": "Unidade não encontrada"}, status=404)

        result = get_material_price_for_unidade(material_id, unidade)
        return JsonResponse(result)


class MaterialListAPIView(LoginRequiredMixin, View):
    """API para listar materiais com preços para uma unidade."""

    def get(self, request):
        unidade_id = request.GET.get("unidade_id")

        if not unidade_id:
            return JsonResponse({"error": "unidade_id é obrigatório"}, status=400)

        try:
            unidade = Unidade.objects.get(pk=unidade_id)
        except Unidade.DoesNotExist:
            return JsonResponse({"error": "Unidade não encontrada"}, status=404)

        materiais = Material.objects.all().order_by("descricao")
        result = []

        for material in materiais:
            price_info = get_material_price_for_unidade(material.id, unidade)
            result.append(
                {
                    "id": material.id,
                    "descricao": material.descricao,
                    "preco": price_info["preco"],
                    "unidade_origem": price_info["unidade_origem"],
                }
            )

        return JsonResponse({"materiais": result})


class UserUnitMixin:
    """Mixin para obter unidades do usuário."""

    def get_user_unidades(self):
        user = self.request.user
        if user.is_superuser:
            return Unidade.objects.all()
        return Unidade.objects.filter(
            id__in=UserUnidade.objects.filter(user=user, status=True).values_list(
                "unidade_id", flat=True
            )
        )


class PedidoCreateView(LoginRequiredMixin, UserUnitMixin, CreateView):
    """View para criar novo pedido."""

    model = Pedido
    form_class = PedidoForm
    template_name = "pedidos/pedido_form.html"
    success_url = reverse_lazy("pedidos:realizados")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filtrar unidades para apenas as do usuário
        form.fields["unidade"].queryset = self.get_user_unidades()
        return form

    def get_initial(self):
        initial = super().get_initial()
        user_unidades = self.get_user_unidades()
        if user_unidades.exists():
            initial["unidade"] = user_unidades.first()
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["material_formset"] = PedidoMaterialFormSet(self.request.POST)
        else:
            context["material_formset"] = PedidoMaterialFormSet()
        context["page_title"] = "Novo Pedido"

        # Passar unidades do usuário com dígito
        user_unidades = self.get_user_unidades()
        unidades_list = [
            {"id": u.id, "nome": u.nome, "digito": int(u.digito) if u.digito else 0}
            for u in user_unidades
        ]
        import json

        context["unidades_data"] = json.dumps(unidades_list)

        # Determinar unidade inicial e buscar preços
        initial_unidade = self.get_initial().get("unidade")
        precos_dict = {}

        # Se formulário já foi submetido (erro), usar a unidade do POST
        if self.request.POST and self.request.POST.get("unidade"):
            try:
                unidade_id = int(self.request.POST.get("unidade"))
                initial_unidade = Unidade.objects.get(pk=unidade_id)
            except (ValueError, Unidade.DoesNotExist):
                pass

        if initial_unidade:
            for material in Material.objects.all():
                price_info = get_material_price_for_unidade(
                    material.id, initial_unidade
                )
                precos_dict[material.id] = price_info["preco"]

        context["initial_prices"] = json.dumps(precos_dict)

        # Passar materiais disponíveis
        materiais_list = list(
            Material.objects.all().order_by("descricao").values("id", "descricao")
        )
        context["materiais"] = json.dumps(materiais_list)

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        material_formset = context["material_formset"]

        if material_formset.is_valid():
            self.object = form.save(commit=False)
            self.object.status = Pedido.Status.NOVO
            self.object.save()

            material_formset.instance = self.object
            material_formset.save()

            messages.success(self.request, "Pedido criado com sucesso!")
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))


class PedidoRecebidosListView(LoginRequiredMixin, UserUnitMixin, ListView):
    """
    Lista pedidos enviados pelas unidades do próximo nível hierárquico
    inferior ao do usuário.
    """

    model = Pedido
    template_name = "pedidos/pedido_list.html"
    context_object_name = "pedidos"
    paginate_by = 20

    def get_queryset(self):
        user_unidades = self.get_user_unidades()
        # Pedidos cujas unidades têm como pai uma das unidades do usuário
        return (
            Pedido.objects.filter(unidade__parent__in=user_unidades)
            .select_related("unidade", "cidade")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Pedidos Recebidos"
        context["status_filter"] = "recebidos"
        return context


class PedidoRealizadosListView(LoginRequiredMixin, UserUnitMixin, ListView):
    """
    Lista pedidos realizados pelas unidades do usuário (Meus Pedidos).
    """

    model = Pedido
    template_name = "pedidos/pedido_list.html"
    context_object_name = "pedidos"
    paginate_by = 20

    def get_queryset(self):
        user_unidades = self.get_user_unidades()
        return (
            Pedido.objects.filter(unidade__in=user_unidades)
            .select_related("unidade", "cidade")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Meus Pedidos"
        context["status_filter"] = "realizados"
        return context


class PedidoSearchView(LoginRequiredMixin, UserUnitMixin, ListView):
    """
    View para busca de pedidos.
    Mostra apenas os pedidos das unidades do próximo nível do usuário
    ou as feitas pela unidade dele.
    """

    model = Pedido
    template_name = "pedidos/pedido_search.html"
    context_object_name = "pedidos"
    paginate_by = 20

    def get_queryset(self):
        user_unidades = self.get_user_unidades()

        # Filtro base: Unidades do usuário OU filhos das unidades do usuário
        from django.db.models import Q

        base_qs = (
            Pedido.objects.filter(
                Q(unidade__in=user_unidades) | Q(unidade__parent__in=user_unidades)
            )
            .select_related("unidade", "cidade")
            .order_by("-created_at")
        )

        # Aplicar filtros do formulário
        solicitante = self.request.GET.get("solicitante")
        cidade = self.request.GET.get("cidade")
        unidade = self.request.GET.get("unidade")
        status = self.request.GET.get("status")
        data_inicio = self.request.GET.get("data_inicio")
        data_fim = self.request.GET.get("data_fim")

        queryset = base_qs

        if solicitante:
            queryset = queryset.filter(solicitante__icontains=solicitante)
        if cidade:
            queryset = queryset.filter(cidade_id=cidade)
        if unidade:
            queryset = queryset.filter(unidade_id=unidade)
        if status:
            queryset = queryset.filter(status=status)
        if data_inicio:
            queryset = queryset.filter(created_at__date__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(created_at__date__lte=data_fim)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Buscar Pedidos"
        context["search_form"] = PedidoSearchForm(self.request.GET or None)
        return context


class PedidoDetailView(LoginRequiredMixin, DetailView):
    """View para detalhes do pedido."""

    model = Pedido
    template_name = "pedidos/pedido_detail.html"
    context_object_name = "pedido"

    def get_queryset(self):
        return Pedido.objects.select_related("unidade", "cidade").prefetch_related(
            "pedidomaterial_set__material"
        )

    # TODO: Adicionar verificação de permissão para ver detalhe apenas se tiver acesso à hierarquia?
    # Por enquanto mantemos o queryset padrão mas num cenário real deveria filtrar.

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Pedido #{self.object.pk}"
        context["materiais"] = self.object.pedidomaterial_set.all()
        return context


class PedidoUpdateStatusView(LoginRequiredMixin, View):
    """View para atualizar status do pedido."""

    def post(self, request, pk):
        pedido = get_object_or_404(Pedido, pk=pk)
        novo_status = request.POST.get("status")

        if novo_status and novo_status.isdigit():
            novo_status = int(novo_status)
            if novo_status in [choice[0] for choice in Pedido.Status.choices]:
                pedido.status = novo_status
                pedido.save()
                messages.success(
                    request, f'Status atualizado para "{pedido.get_status_display()}"!'
                )
            else:
                messages.error(request, "Status inválido.")
        else:
            messages.error(request, "Status não informado.")

        return redirect("pedidos:detail", pk=pk)
