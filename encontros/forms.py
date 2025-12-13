from django import forms
from .models import Encontro, CasalEncontro
from paroquias.models import Paroquia
from casais.models import Casal
from equipes.models import Equipe


class EncontroForm(forms.ModelForm):
    """Formulário para criar/editar encontros."""

    class Meta:
        model = Encontro
        fields = ["unidade", "nome", "etapa", "data", "quadrante", "paroquia"]
        widgets = {
            "unidade": forms.Select(attrs={"class": "form-select"}),
            "nome": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nome do encontro"}
            ),
            "etapa": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "placeholder": "Etapa"}
            ),
            "data": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "quadrante": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "1",
                    "placeholder": "Quadrante (opcional)",
                }
            ),
            "paroquia": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "unidade": "Unidade",
            "nome": "Nome",
            "etapa": "Etapa",
            "data": "Data",
            "quadrante": "Quadrante",
            "paroquia": "Paróquia",
        }

    def __init__(self, *args, user_unidades=None, **kwargs):
        super().__init__(*args, **kwargs)

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

        # Configurar paróquias
        if self.instance and self.instance.pk:
            # Edição - filtrar por unidade do encontro
            self.fields["paroquia"].queryset = Paroquia.objects.filter(
                unidade=self.instance.unidade
            ).order_by("nome")
        else:
            # Criação - mostrar todas inicialmente
            self.fields["paroquia"].queryset = Paroquia.objects.order_by("nome")


class CasalEncontroForm(forms.ModelForm):
    """Formulário para adicionar casal ao encontro."""

    class Meta:
        model = CasalEncontro
        fields = ["casal", "equipe"]
        widgets = {
            "casal": forms.Select(attrs={"class": "form-select"}),
            "equipe": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "casal": "Casal",
            "equipe": "Equipe",
        }

    def __init__(self, *args, encontro=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipe"].queryset = Equipe.objects.order_by("nome")
        self.fields["equipe"].required = False

        if encontro:
            # Excluir casais já vinculados
            casais_existentes = encontro.casais.values_list("id", flat=True)
            self.fields["casal"].queryset = Casal.objects.exclude(
                id__in=casais_existentes
            ).order_by("ele")
        else:
            self.fields["casal"].queryset = Casal.objects.order_by("ele")


class EncontroBuscaForm(forms.Form):
    """Formulário de busca de encontros."""

    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Buscar por nome..."}
        ),
        label="Busca",
    )
    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label="Data Início",
    )
    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label="Data Fim",
    )
