from django import forms
from django.contrib.auth import get_user_model
from .models import Unidade, UserUnidade

User = get_user_model()


class UnidadeForm(forms.ModelForm):
    """Formulário para criar/editar unidades."""

    class Meta:
        model = Unidade
        fields = [
            "nome",
            "digito",
            "vencimento",
            "bloqueado",
            "tipo",
            "status",
            "parent",
        ]
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nome da unidade"}
            ),
            "digito": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Dígito"}
            ),
            "vencimento": forms.NumberInput(attrs={"class": "form-control"}),
            "bloqueado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "status": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Filtrar tipos disponíveis baseado no nível do usuário
        if user and not user.is_superuser:
            user_unidades = UserUnidade.objects.filter(
                user=user, status=True
            ).select_related("unidade")
            if user_unidades.exists():
                # Pegar o menor tipo (maior hierarquia) do usuário
                min_tipo = min(uu.unidade.tipo for uu in user_unidades)
                # Só pode criar unidades de nível abaixo
                allowed_tipos = [
                    (t.value, t.label) for t in Unidade.Tipo if t.value > min_tipo
                ]
                self.fields["tipo"].choices = allowed_tipos

                # Filtrar parent para unidades que o usuário tem acesso
                user_unidade_ids = [uu.unidade_id for uu in user_unidades]
                self.fields["parent"].queryset = Unidade.objects.filter(
                    id__in=user_unidade_ids
                )


class AddUserByEmailForm(forms.Form):
    """Formulário para adicionar usuário por email."""

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Digite o email do usuário"}
        ),
        label="Email do Usuário",
    )
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nome (opcional se usuário já existir)",
            }
        ),
        label="Nome",
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Telefone (opcional)",
                "data-mask": "(00) 00000-0000",
            }
        ),
        label="Telefone",
    )


class UserProfileForm(forms.ModelForm):
    """Formulário para edição de dados do perfil do usuário."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(
                attrs={"class": "form-control", "data-mask": "(00) 00000-0000"}
            ),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }
        labels = {
            "first_name": "Nome",
            "last_name": "Telefone",
            "email": "Email",
        }
