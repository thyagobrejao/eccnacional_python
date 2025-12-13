from django import forms
from .models import Casal


class CasalForm(forms.ModelForm):
    """Formulário para criar/editar casais."""

    class Meta:
        model = Casal
        fields = [
            "ele",
            "ela",
            "email_ele",
            "email_ela",
            "telefone_ele",
            "telefone_ela",
            "obs",
            "foto",
            "paroquia",
        ]
        widgets = {
            "ele": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nome dele"}
            ),
            "ela": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nome dela"}
            ),
            "email_ele": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "E-mail dele"}
            ),
            "email_ela": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "E-mail dela"}
            ),
            "telefone_ele": forms.TextInput(
                attrs={
                    "class": "form-control phone-mask",
                    "placeholder": "(00) 00000-0000",
                }
            ),
            "telefone_ela": forms.TextInput(
                attrs={
                    "class": "form-control phone-mask",
                    "placeholder": "(00) 00000-0000",
                }
            ),
            "obs": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Observações (opcional)",
                }
            ),
            "foto": forms.FileInput(attrs={"class": "form-control"}),
            "paroquia": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "ele": "Nome dele",
            "ela": "Nome dela",
            "email_ele": "E-mail dele",
            "email_ela": "E-mail dela",
            "telefone_ele": "Telefone dele",
            "telefone_ela": "Telefone dela",
            "obs": "Observações",
            "foto": "Foto do casal",
            "paroquia": "Paróquia",
        }


class CasalBuscaForm(forms.Form):
    """Formulário de busca de casais."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Buscar por nome..."}
        ),
        label="Busca por nome",
    )
    email = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "E-mail..."}
        ),
        label="E-mail",
    )
    telefone = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control phone-mask", "placeholder": "(00) 00000-0000"}
        ),
        label="Telefone",
    )
    paroquia = forms.ModelChoiceField(
        required=False,
        queryset=None,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Paróquia",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from paroquias.models import Paroquia

        self.fields["paroquia"].queryset = Paroquia.objects.order_by("nome")
