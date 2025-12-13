from django import forms
from .models import Equipe


class EquipeForm(forms.ModelForm):
    """Formulário para criar/editar equipes."""

    class Meta:
        model = Equipe
        fields = ["nome"]
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nome da equipe"}
            ),
        }
        labels = {
            "nome": "Nome",
        }
