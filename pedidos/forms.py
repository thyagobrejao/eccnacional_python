from django import forms
from django.forms import inlineformset_factory
from .models import Pedido, PedidoMaterial
from unidades.models import Unidade
from municipios.models import Cidade


class PedidoForm(forms.ModelForm):
    """Formulário para criação e edição de pedidos."""

    class Meta:
        model = Pedido
        fields = [
            "solicitante",
            "unidade",
            "cidade",
            "endereco",
            "cep",
            "telefones",
            "obs",
        ]
        widgets = {
            "solicitante": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nome do solicitante"}
            ),
            "unidade": forms.Select(attrs={"class": "form-select"}),
            "cidade": forms.Select(attrs={"class": "form-select", "id": "id_cidade"}),
            "endereco": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Endereço completo"}
            ),
            "cep": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "00000-000"}
            ),
            "telefones": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "(00) 00000-0000"}
            ),
            "obs": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Observações adicionais",
                }
            ),
        }
        labels = {
            "solicitante": "Solicitante",
            "unidade": "Unidade",
            "cidade": "Cidade",
            "endereco": "Endereço",
            "cep": "CEP",
            "telefones": "Telefones",
            "obs": "Observações",
        }


class PedidoMaterialForm(forms.ModelForm):
    """Formulário para materiais do pedido."""

    class Meta:
        model = PedidoMaterial
        fields = ["material", "quantidade", "valor_venda"]
        widgets = {
            "material": forms.Select(attrs={"class": "form-select"}),
            "quantidade": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "placeholder": "Qtd"}
            ),
            "valor_venda": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"}
            ),
        }


# Formset para materiais do pedido
PedidoMaterialFormSet = inlineformset_factory(
    Pedido,
    PedidoMaterial,
    form=PedidoMaterialForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class PedidoSearchForm(forms.Form):
    """Formulário de busca de pedidos."""

    solicitante = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nome do solicitante"}
        ),
    )
    cidade = forms.ModelChoiceField(
        queryset=Cidade.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_cidade_search"}),
    )
    unidade = forms.ModelChoiceField(
        queryset=Unidade.objects.all(),
        required=False,
        empty_label="Todas as unidades",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        choices=[("", "Todos os status")] + list(Pedido.Status.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
