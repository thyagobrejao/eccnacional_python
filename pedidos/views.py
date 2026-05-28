import json
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from materiais.models import Material, UnidadeMaterial
from unidades.models import Unidade, UserUnidade

from .forms import PedidoForm, PedidoMaterialFormSet, PedidoSearchForm
from .models import Pedido
from eccnacional.emailing import (
    send_new_order_notifications,
    send_payment_confirmation_notifications,
    send_stock_notifications,
)


logger = logging.getLogger(__name__)


def calculate_pedido_totals(items, unidade):
    subtotal = Decimal("0.00")

    for item in items:
        if isinstance(item, dict):
            quantidade = item["quantidade"]
            valor_venda = item["valor_venda"]
        else:
            quantidade = item.quantidade
            valor_venda = item.valor_venda or Decimal("0.00")

        subtotal += valor_venda * quantidade

    total_arredondado = subtotal.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    digito = Decimal(unidade.digito or 0)
    total_final = total_arredondado + (digito / Decimal("100"))

    return {
        "subtotal": subtotal,
        "total_arredondado": total_arredondado,
        "digito": digito,
        "total_final": total_final,
    }


def get_material_price_for_unidade(material_id, unidade):
    """
    Busca o preço do material apenas na unidade pai imediata.
    """
    parent_unidade = unidade.parent
    if not parent_unidade:
        return {
            "preco": Decimal("0.00"),
            "unidade_origem": None,
            "unidade_tipo": None,
        }

    um = UnidadeMaterial.objects.filter(
        material_id=material_id,
        unidade=parent_unidade,
    ).first()

    if not um or um.valor is None:
        return {
            "preco": Decimal("0.00"),
            "unidade_origem": None,
            "unidade_tipo": None,
        }

    return {
        "preco": um.valor,
        "unidade_origem": parent_unidade.nome,
        "unidade_tipo": parent_unidade.get_tipo_display(),
    }


class MaterialPriceAPIView(LoginRequiredMixin, View):
    """API para buscar preço de material com base na hierarquia de unidades."""

    def get(self, request):
        material_id = request.GET.get("material_id")
        unidade_id = request.GET.get("unidade_id")

        if not material_id or not unidade_id:
            return JsonResponse(
                {"error": "material_id e unidade_id são obrigatórios"}, status=400
            )

        user_unidades = Unidade.objects.all() if request.user.is_superuser else Unidade.objects.filter(
            id__in=UserUnidade.objects.filter(user=request.user, status=True).values_list(
                "unidade_id", flat=True
            )
        )
        unidade = user_unidades.select_related("parent").filter(pk=unidade_id).first()
        if not unidade:
            return JsonResponse({"error": "Unidade não encontrada"}, status=404)

        result = get_material_price_for_unidade(material_id, unidade)
        result["preco"] = float(result["preco"])
        return JsonResponse(result)


class MaterialListAPIView(LoginRequiredMixin, View):
    """API para listar materiais com preços para uma unidade."""

    def get(self, request):
        unidade_id = request.GET.get("unidade_id")

        if not unidade_id:
            return JsonResponse({"error": "unidade_id é obrigatório"}, status=400)

        user_unidades = Unidade.objects.all() if request.user.is_superuser else Unidade.objects.filter(
            id__in=UserUnidade.objects.filter(user=request.user, status=True).values_list(
                "unidade_id", flat=True
            )
        )
        unidade = user_unidades.select_related("parent").filter(pk=unidade_id).first()
        if not unidade:
            return JsonResponse({"error": "Unidade não encontrada"}, status=404)

        materiais = Material.objects.all().order_by("descricao")
        result = []

        for material in materiais:
            price_info = get_material_price_for_unidade(material.id, unidade)
            result.append(
                {
                    "id": material.id,
                    "descricao": material.descricao,
                    "preco": float(price_info["preco"]),
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

    def get_user_unidade_ids(self):
        if not hasattr(self, "_user_unidade_ids"):
            self._user_unidade_ids = set(
                self.get_user_unidades().values_list("id", flat=True)
            )
        return self._user_unidade_ids

    def get_immediate_child_unidade_ids(self):
        if not hasattr(self, "_immediate_child_unidade_ids"):
            self._immediate_child_unidade_ids = set(
                Unidade.objects.filter(
                    parent_id__in=self.get_user_unidade_ids()
                ).values_list("id", flat=True)
            )
        return self._immediate_child_unidade_ids

    def get_visible_unidade_ids(self):
        return self.get_user_unidade_ids() | self.get_immediate_child_unidade_ids()

    def can_update_received_pedido(self, pedido):
        return bool(pedido.unidade_id and pedido.unidade_id in self.get_immediate_child_unidade_ids())


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

    def build_prices_by_unidade(self, unidades, materiais):
        parent_ids = {unidade.parent_id for unidade in unidades if unidade.parent_id}
        if not parent_ids or not materiais:
            return {str(unidade.id): {} for unidade in unidades}

        unidade_material_rows = UnidadeMaterial.objects.filter(
            unidade_id__in=parent_ids,
            material_id__in=[material.id for material in materiais],
        ).values("unidade_id", "material_id", "valor")

        parent_prices = {
            (row["unidade_id"], row["material_id"]): float(row["valor"] or 0)
            for row in unidade_material_rows
        }

        prices_by_unidade = {}
        for unidade in unidades:
            unidade_prices = {}
            if unidade.parent_id:
                for material in materiais:
                    unidade_prices[str(material.id)] = parent_prices.get(
                        (unidade.parent_id, material.id),
                        0.0,
                    )
            prices_by_unidade[str(unidade.id)] = unidade_prices

        return prices_by_unidade

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        material_formset = kwargs.get("material_formset")
        if material_formset is None:
            if self.request.POST:
                material_formset = PedidoMaterialFormSet(self.request.POST)
            else:
                material_formset = PedidoMaterialFormSet()

        context["material_formset"] = material_formset
        context["page_title"] = "Novo Pedido"

        # Passar unidades do usuário com dígito
        user_unidades = list(self.get_user_unidades().select_related("parent"))
        unidades_list = [
            {"id": u.id, "nome": u.nome, "digito": int(u.digito) if u.digito else 0}
            for u in user_unidades
        ]
        context["unidades_data"] = json.dumps(unidades_list)

        materiais = list(Material.objects.all().order_by("descricao"))
        prices_by_unidade = self.build_prices_by_unidade(user_unidades, materiais)
        context["prices_by_unidade"] = json.dumps(prices_by_unidade)

        # Determinar unidade inicial e buscar preços
        initial_unidade = self.get_initial().get("unidade")
        precos_dict = {}

        # Se formulário já foi submetido (erro), usar a unidade do POST
        if self.request.POST and self.request.POST.get("unidade"):
            try:
                unidade_id = int(self.request.POST.get("unidade"))
                initial_unidade = next(
                    (unidade for unidade in user_unidades if unidade.id == unidade_id),
                    None,
                )
            except ValueError:
                pass

        if initial_unidade:
            precos_dict = prices_by_unidade.get(str(initial_unidade.id), {})

        context["initial_prices"] = json.dumps(precos_dict)

        # Passar materiais disponíveis
        materiais_list = list(
            material for material in materiais
        )
        context["materiais"] = json.dumps([
            {"id": material.id, "descricao": material.descricao}
            for material in materiais_list
        ])
        context["initial_material_rows"] = json.dumps(
            self.get_initial_material_rows(material_formset)
        )

        return context

    def get_initial_material_rows(self, material_formset):
        rows = []

        for material_form in material_formset.forms:
            material_id = material_form["material"].value()
            quantidade = material_form["quantidade"].value()
            valor_venda = material_form["valor_venda"].value()

            if not any([material_id, quantidade, valor_venda]):
                continue

            rows.append(
                {
                    "material_id": int(material_id) if material_id else None,
                    "quantidade": quantidade or 1,
                    "valor_venda": str(valor_venda or "0.00"),
                }
            )

        return rows

    def get_preview_post_fields(self):
        fields = []

        for name, values in self.request.POST.lists():
            if name in {"csrfmiddlewaretoken", "submission_step"}:
                continue

            for value in values:
                fields.append({"name": name, "value": value})

        return fields

    def build_preview_context(self, form, material_formset):
        pedido_items = []

        for cleaned_data in material_formset.cleaned_data:
            if not cleaned_data or cleaned_data.get("DELETE"):
                continue

            subtotal = cleaned_data["valor_venda"] * cleaned_data["quantidade"]
            pedido_items.append(
                {
                    "material": cleaned_data["material"],
                    "quantidade": cleaned_data["quantidade"],
                    "valor_venda": cleaned_data["valor_venda"],
                    "subtotal": subtotal,
                }
            )

        pedido_total_info = calculate_pedido_totals(
            pedido_items, form.cleaned_data["unidade"]
        )

        return {
            "page_title": "Conferir Pedido",
            "pedido_preview": form.cleaned_data,
            "pedido_items_preview": pedido_items,
            "pedido_total_info": pedido_total_info,
            "preview_post_fields": self.get_preview_post_fields(),
        }

    def apply_immediate_parent_prices(self, material_formset, unidade):
        for material_form in material_formset.forms:
            cleaned_data = getattr(material_form, "cleaned_data", None)
            if not cleaned_data or cleaned_data.get("DELETE"):
                continue

            price_info = get_material_price_for_unidade(
                cleaned_data["material"].id,
                unidade,
            )
            valor_venda = price_info["preco"]
            if not isinstance(valor_venda, Decimal):
                valor_venda = Decimal(str(valor_venda or "0.00"))
            valor_venda = valor_venda.quantize(Decimal("0.01"))

            cleaned_data["valor_venda"] = valor_venda
            material_form.instance.valor_venda = valor_venda

    def save_pedido(self, form, material_formset):
        self.object = form.save(commit=False)
        self.object.status = Pedido.Status.NOVO
        self.object.save()

        material_formset.instance = self.object
        material_formset.save()

        emails_sent = send_new_order_notifications(self.object)
        if emails_sent:
            messages.success(
                self.request,
                f"Pedido criado com sucesso! {emails_sent} notificação(ões) enviada(s).",
            )
        else:
            messages.success(self.request, "Pedido criado com sucesso!")

        return redirect(self.success_url)

    def form_invalid(self, form, material_formset=None):
        return self.render_to_response(
            self.get_context_data(form=form, material_formset=material_formset)
        )

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        material_formset = PedidoMaterialFormSet(self.request.POST)
        submission_step = self.request.POST.get("submission_step")

        if submission_step == "edit":
            return self.render_to_response(
                self.get_context_data(form=form, material_formset=material_formset)
            )

        if not form.is_valid() or not material_formset.is_valid():
            return self.form_invalid(form, material_formset)

        self.apply_immediate_parent_prices(
            material_formset,
            form.cleaned_data["unidade"],
        )

        if submission_step == "confirm":
            return self.save_pedido(form, material_formset)

        return render(
            request,
            "pedidos/pedido_confirm.html",
            self.build_preview_context(form, material_formset),
        )


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
        return (
            Pedido.objects.filter(unidade_id__in=self.get_immediate_child_unidade_ids())
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
        base_qs = (
            Pedido.objects.filter(
                Q(unidade_id__in=self.get_visible_unidade_ids())
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
        search_form = PedidoSearchForm(self.request.GET or None)
        search_form.fields["unidade"].queryset = Unidade.objects.filter(
            id__in=self.get_visible_unidade_ids()
        ).order_by("nome")
        context["search_form"] = search_form
        return context


class PedidoDetailView(LoginRequiredMixin, UserUnitMixin, DetailView):
    """View para detalhes do pedido."""

    model = Pedido
    template_name = "pedidos/pedido_detail.html"
    context_object_name = "pedido"

    def get_queryset(self):
        return (
            Pedido.objects.filter(
                Q(unidade_id__in=self.get_visible_unidade_ids())
            )
            .select_related("unidade", "cidade")
            .prefetch_related("pedidomaterial_set__material")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Pedido #{self.object.pk}"
        context["materiais"] = self.object.pedidomaterial_set.all()
        context["can_update_status"] = self.can_update_received_pedido(self.object)
        return context


class PedidoUpdateStatusView(LoginRequiredMixin, UserUnitMixin, View):
    """View para atualizar status do pedido."""

    def post(self, request, pk):
        pedido = get_object_or_404(
            Pedido,
            Q(unidade_id__in=self.get_visible_unidade_ids()),
            pk=pk,
        )

        if not self.can_update_received_pedido(pedido):
            messages.error(
                request,
                "Apenas a unidade que recebeu o pedido pode atualizar o status.",
            )
            return redirect("pedidos:detail", pk=pk)

        old_status = pedido.status
        novo_status = request.POST.get("status")

        if novo_status and novo_status.isdigit():
            novo_status = int(novo_status)
            if novo_status in [choice[0] for choice in Pedido.Status.choices]:
                pedido.status = novo_status
                pedido.save()

                if old_status < Pedido.Status.REALIZADO and novo_status in [
                    Pedido.Status.RECEBIDO,
                    Pedido.Status.REALIZADO,
                ]:
                    send_stock_notifications(pedido, movement_label="Entrada")

                if (
                    old_status == Pedido.Status.RECEBIDO
                    and novo_status == Pedido.Status.REALIZADO
                ):
                    send_payment_confirmation_notifications(pedido)

                messages.success(
                    request, f'Status atualizado para "{pedido.get_status_display()}"!'
                )
            else:
                messages.error(request, "Status inválido.")
        else:
            messages.error(request, "Status não informado.")

        return redirect("pedidos:detail", pk=pk)
