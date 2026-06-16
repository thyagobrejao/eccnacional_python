from django import forms
from .models import Noticia, Estatistica, Regional, ColaboradorNoticia
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


# ─── Formulários do Sistema de Colaboradores ─────────────────────────────────

class LoginMagicLinkForm(forms.Form):
    """Formulário de login por magic link — apenas campo de e-mail"""
    email = forms.EmailField(
        label="Seu E-mail",
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'seu@email.com',
            'autofocus': True,
        }),
    )


class ColaboradorNoticiaForm(forms.ModelForm):
    """Formulário CRUD de colaboradores (usado por revisores)"""
    class Meta:
        model = ColaboradorNoticia
        fields = ['nome', 'email', 'regiao', 'perfil', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Nome completo'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control', 'placeholder': 'email@exemplo.com'
            }),
            'regiao': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ex: Regional Sul 1'
            }),
            'perfil': forms.Select(attrs={'class': 'form-select'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class NoticiaColaboradorForm(forms.ModelForm):
    """Formulário simplificado para colaboradores criarem/editarem notícias"""

    content = forms.CharField(
        widget=TinyMCE(
            attrs={'cols': 80, 'rows': 30},
            mce_attrs={
                'images_upload_handler': (
                    "function(blobInfo) {"
                    " return new Promise(function(resolve, reject) {"
                    "  var fd = new FormData();"
                    "  fd.append('file', blobInfo.blob(), blobInfo.filename());"
                    "  var csrfToken = '';"
                    "  var csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');"
                    "  if (csrfInput) { csrfToken = csrfInput.value; }"
                    "  else { var m = document.cookie.match(/csrftoken=([^;]+)/); if (m) csrfToken = m[1]; }"
                    "  fetch('/noticias/tinymce/upload/', {"
                    "   method: 'POST',"
                    "   headers: {'X-CSRFToken': csrfToken},"
                    "   body: fd,"
                    "   credentials: 'same-origin'"
                    "  })"
                    "  .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })"
                    "  .then(function(data) {"
                    "   if (data.location) { resolve(data.location); }"
                    "   else { reject('Upload falhou: ' + (data.error || 'Erro desconhecido')); }"
                    "  })"
                    "  .catch(function(e) { reject('Upload falhou: ' + e); });"
                    " });"
                    "}"
                ),
                'file_picker_callback': (
                    "function(callback, value, meta) {"
                    " if (meta.filetype === 'image') {"
                    "  var input = document.createElement('input');"
                    "  input.setAttribute('type', 'file');"
                    "  input.setAttribute('accept', 'image/*');"
                    "  input.onchange = function() {"
                    "   var file = this.files[0];"
                    "   var fd = new FormData();"
                    "   fd.append('file', file);"
                    "   var csrfToken = '';"
                    "   var csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');"
                    "   if (csrfInput) { csrfToken = csrfInput.value; }"
                    "   else { var m = document.cookie.match(/csrftoken=([^;]+)/); if (m) csrfToken = m[1]; }"
                    "   fetch('/noticias/tinymce/upload/', {"
                    "    method: 'POST',"
                    "    headers: {'X-CSRFToken': csrfToken},"
                    "    body: fd,"
                    "    credentials: 'same-origin'"
                    "   })"
                    "   .then(function(r) { return r.json(); })"
                    "   .then(function(data) {"
                    "    if (data.location) { callback(data.location, {title: file.name}); }"
                    "   });"
                    "  };"
                    "  input.click();"
                    " }"
                    "}"
                )
            }
        ),
        label='Conteúdo'
    )

    class Meta:
        model = Noticia
        fields = ['titulo', 'content', 'imagem_principal']
        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o título da notícia'
            }),
            'imagem_principal': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
        labels = {
            'titulo': 'Título',
            'imagem_principal': 'Imagem Principal',
        }
        help_texts = {
            'imagem_principal': 'Selecione uma imagem para ser o destaque da notícia',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['ativa']:
                if not hasattr(field.widget.attrs, 'class'):
                    field.widget.attrs.setdefault('class', 'form-control')