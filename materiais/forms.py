from django import forms
from .models import Material, UnidadeMaterial


class MaterialForm(forms.ModelForm):
    """Formulário para criar/editar materiais (apenas Nacional)."""

    class Meta:
        model = Material
        fields = ["descricao"]
        widgets = {
            "descricao": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Descrição do material"}
            ),
        }
        labels = {
            "descricao": "Descrição",
        }


class UnidadeMaterialForm(forms.ModelForm):
    """Formulário para definir preço do material por unidade."""

    class Meta:
        model = UnidadeMaterial
        fields = ["valor", "quantidade"]
        widgets = {
            "valor": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"}
            ),
            "quantidade": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "placeholder": "0"}
            ),
        }
        labels = {
            "valor": "Valor (R$)",
            "quantidade": "Quantidade em Estoque",
        }
