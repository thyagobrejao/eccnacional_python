from django import forms
from .models import Noticia
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