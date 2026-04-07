from django import forms
from .models import Noticia, Estatistica, Regional
from tinymce.widgets import TinyMCE


class NoticiaForm(forms.ModelForm):
    """Formulário para criação e edição de notícias"""
    
    content = forms.CharField(
        widget=TinyMCE(attrs={'cols': 80, 'rows': 30}),
        label='Conteúdo'
    )
    
    class Meta:
        model = Noticia
        fields = ['titulo', 'content', 'imagem_principal', 'especial', 'ativa']
        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o título da notícia'
            }),
            'imagem_principal': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'especial': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ativa': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'titulo': 'Título',
            'imagem_principal': 'Imagem Principal',
            'especial': 'Notícia Especial',
            'ativa': 'Ativa'
        }
        help_texts = {
            'imagem_principal': 'Selecione uma imagem para ser o destaque da notícia',
            'especial': 'Marque esta opção se a notícia deve ser destacada',
            'ativa': 'Desmarque para ocultar a notícia do site'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adiciona classes CSS aos campos
        for field_name, field in self.fields.items():
            if field_name not in ['especial', 'ativa']:
                field.widget.attrs.update({'class': 'form-control'})


class ContatoForm(forms.Form):
    nome = forms.CharField(
        max_length=100,
        label="Seu Nome",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu nome completo'}),
    )
    email = forms.EmailField(
        label="Seu E-mail",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'seu@email.com'}),
    )
    assunto = forms.CharField(
        max_length=200,
        required=False,
        label="Assunto",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assunto da mensagem'}),
    )
    mensagem = forms.CharField(
        label="Sua Mensagem",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Digite sua mensagem...'}),
    )


class EstatisticaForm(forms.ModelForm):
    class Meta:
        model = Estatistica
        fields = ['ano', 'imagem', 'arquivo']
        widgets = {
            'ano': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 2024'}),
            'imagem': forms.FileInput(attrs={'class': 'form-control'}),
            'arquivo': forms.FileInput(attrs={'class': 'form-control'}),
        }


class RegionalForm(forms.ModelForm):
    class Meta:
        model = Regional
        fields = ['nome', 'regional_id', 'descricao', 'casal', 'padre', 'imagem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'regional_id': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'casal': forms.TextInput(attrs={'class': 'form-control'}),
            'padre': forms.TextInput(attrs={'class': 'form-control'}),
            'imagem': forms.FileInput(attrs={'class': 'form-control'}),
        }