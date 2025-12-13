from django import forms
from .models import Paroquia
from municipios.models import Cidade


class ParoquiaForm(forms.ModelForm):
    """Formulário para criar/editar paróquias."""

    class Meta:
        model = Paroquia
        fields = ["unidade", "nome", "bairro", "cidade"]
        widgets = {
            "unidade": forms.Select(attrs={"class": "form-select"}),
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nome da paróquia"}
            ),
            "bairro": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Bairro (opcional)"}
            ),
            "cidade": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "unidade": "Unidade",
            "nome": "Nome",
            "bairro": "Bairro",
            "cidade": "Cidade",
        }

    def __init__(self, *args, user_unidades=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cidade"].queryset = Cidade.objects.order_by("nome")

        # Configurar unidades disponíveis
        if user_unidades:
            from unidades.models import Unidade

            self.fields["unidade"].queryset = Unidade.objects.filter(
                id__in=user_unidades
            ).order_by("nome")

            # Se só tem uma unidade, definir como padrão e ocultar campo
            if len(user_unidades) == 1:
                self.fields["unidade"].initial = user_unidades[0]
                self.fields["unidade"].widget = forms.HiddenInput()
