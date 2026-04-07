from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, CreateView, UpdateView, DeleteView, ListView, DetailView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.conf import settings
import uuid
import os
import re
from .models import Noticia, Estatistica, Regional
from .forms import NoticiaForm, ContatoForm, EstatisticaForm, RegionalForm


class BlogHomeView(TemplateView):
    template_name = 'blog/index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Busca por notícias
        search_query = self.request.GET.get('search', '')
        noticias_list = Noticia.objects.filter(ativa=True, especial=False).order_by('-data_criacao')
        
        if search_query:
            noticias_list = self._apply_search_filter(noticias_list, search_query)
        
        # Paginação
        paginator = Paginator(noticias_list, 12)  # 12 notícias por página
        page_number = self.request.GET.get('page')
        noticias = paginator.get_page(page_number)
        
        context.update({
            'page_title': 'ECC Nacional - Encontro de Casais com Cristo',
            'hero_title': 'Encontro de Casais com Cristo',
            'hero_subtitle': 'Fortalecendo famílias através da fé e do amor cristão',
            'noticias': noticias,
            'search_query': search_query
        })
        
        return context
    
    def _apply_search_filter(self, queryset, search_query):
        """
        Aplica filtros de busca avançados:
        - Busca por termos exatos entre aspas
        - Busca por palavras individuais (qualquer caractere)
        - Suporte para PostgreSQL com busca case-insensitive
        """
        search_query = search_query.strip()
        
        if not search_query:
            return queryset
        
        # Verificar se há termos entre aspas para busca exata
        exact_terms = re.findall(r'"([^"]+)"', search_query)
        # Remover termos entre aspas da query original
        remaining_query = re.sub(r'"[^"]+"', '', search_query).strip()
        
        # Construir filtros
        filters = Q()
        
        # Busca por termos exatos
        for exact_term in exact_terms:
            exact_term = exact_term.strip()
            if exact_term:
                filters |= (
                    Q(titulo__icontains=exact_term) | 
                    Q(content__icontains=exact_term)
                )
        
        # Busca por palavras individuais do restante da query
        if remaining_query:
            # Dividir em palavras e buscar cada uma
            words = remaining_query.split()
            for word in words:
                word = word.strip()
                if word:
                    filters |= (
                        Q(titulo__icontains=word) | 
                        Q(content__icontains=word)
                    )
        
        # Se não há filtros específicos, fazer busca geral
        if not filters:
            filters = (
                Q(titulo__icontains=search_query) | 
                Q(content__icontains=search_query)
            )
        
        return queryset.filter(filters)


class NoticiasEspeciaisView(TemplateView):
    template_name = 'blog/noticias_especiais.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Buscar apenas notícias especiais ativas
        noticias_especiais = Noticia.objects.filter(ativa=True, especial=True).order_by('-data_criacao')
        
        # Paginação
        paginator = Paginator(noticias_especiais, 12)  # 12 notícias por página
        page_number = self.request.GET.get('page')
        noticias = paginator.get_page(page_number)
        
        context.update({
            'page_title': 'Conheça o ECC - Notícias Especiais',
            'hero_title': 'Conheça o ECC',
            'hero_subtitle': 'Notícias especiais sobre o Encontro de Casais com Cristo',
            'noticias': noticias,
            'hide_search': True  # Flag para ocultar a barra de busca
        })
        
        return context


class NoticiaDetailView(DetailView):
    """Exibe o detalhe de uma notícia"""
    model = Noticia
    template_name = 'blog/noticia_detail.html'
    context_object_name = 'noticia'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        return Noticia.objects.filter(ativa=True)


class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin para restringir acesso apenas a administradores"""
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff
    
    def handle_no_permission(self):
        messages.error(self.request, 'Acesso negado. Apenas administradores podem acessar esta página.')
        return redirect('admin:login')


class NoticiaListView(AdminRequiredMixin, ListView):
    """Lista todas as notícias para administradores"""
    model = Noticia
    template_name = 'blog/admin/noticia_list.html'
    context_object_name = 'noticias'
    paginate_by = 10
    ordering = ['-data_criacao']


class NoticiaCreateView(AdminRequiredMixin, CreateView):
    """Criar nova notícia"""
    model = Noticia
    form_class = NoticiaForm
    template_name = 'blog/admin/noticia_form.html'
    success_url = reverse_lazy('blog:admin_noticia_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Notícia criada com sucesso!')
        return super().form_valid(form)


class NoticiaUpdateView(AdminRequiredMixin, UpdateView):
    """Editar notícia existente"""
    model = Noticia
    form_class = NoticiaForm
    template_name = 'blog/admin/noticia_form.html'
    success_url = reverse_lazy('blog:admin_noticia_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Notícia atualizada com sucesso!')
        return super().form_valid(form)


class NoticiaDeleteView(AdminRequiredMixin, DeleteView):
    """Deletar notícia"""
    model = Noticia
    template_name = 'blog/admin/noticia_confirm_delete.html'
    success_url = reverse_lazy('blog:admin_noticia_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Notícia deletada com sucesso!')
        return super().delete(request, *args, **kwargs)


@csrf_exempt
def tinymce_upload(request):
    """View para upload de imagens do TinyMCE para S3"""
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            from datetime import datetime
            
            uploaded_file = request.FILES['file']
            
            # Obter o ambiente do sistema (development, production, etc.)
            environment = getattr(settings, 'ENVIRONMENT', 'development')
            
            # Obter data atual para criar estrutura de pastas ANO/MES/DIA
            now = datetime.now()
            year = now.strftime('%Y')
            month = now.strftime('%m')
            day = now.strftime('%d')
            
            # Gerar nome único para o arquivo
            file_extension = os.path.splitext(uploaded_file.name)[1]
            unique_filename = f"{environment}/tinymce/{year}/{month}/{day}/{uuid.uuid4()}{file_extension}"
            
            # Salvar no S3 usando o storage padrão
            file_path = default_storage.save(unique_filename, uploaded_file)
            file_url = default_storage.url(file_path)
            
            return JsonResponse({
                'location': file_url
            })
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'error': 'Método não permitido ou arquivo não encontrado'
    }, status=400)


def tinymce_file_browser_view(request):
    """View para exibir o navegador de arquivos do TinyMCE"""
    return render(request, 'blog/admin/tinymce_file_browser.html')


@csrf_exempt
def tinymce_file_browser(request):
    """View para navegação de arquivos já enviados no S3"""
    try:
        from boto3 import client
        from collections import defaultdict
        
        # Obter o ambiente do sistema
        environment = getattr(settings, 'ENVIRONMENT', 'development')
        
        # Obter o caminho atual da navegação
        current_path = request.GET.get('path', '')
        
        # Configurar cliente S3
        s3_client = client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        # Construir o prefixo baseado no caminho atual
        base_prefix = f"{environment}/tinymce/"
        if current_path:
            prefix = f"{base_prefix}{current_path}/"
        else:
            prefix = base_prefix
        
        # Listar objetos no S3
        response = s3_client.list_objects_v2(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Prefix=prefix,
            Delimiter='/'
        )
        
        folders = []
        files = []
        
        # Processar pastas (CommonPrefixes)
        if 'CommonPrefixes' in response:
            for prefix_info in response['CommonPrefixes']:
                folder_path = prefix_info['Prefix']
                # Remover o prefixo base para obter apenas o nome da pasta
                folder_name = folder_path.replace(base_prefix, '').rstrip('/')
                if current_path:
                    folder_name = folder_name.replace(current_path + '/', '')
                
                folders.append({
                    'name': folder_name,
                    'path': folder_path.replace(base_prefix, '').rstrip('/'),
                    'type': 'folder'
                })
        
        # Processar arquivos
        if 'Contents' in response:
            for obj in response['Contents']:
                # Pular se for apenas o diretório
                if obj['Key'].endswith('/'):
                    continue
                    
                if obj['Key'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    file_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}/{obj['Key']}"
                    filename = os.path.basename(obj['Key'])
                    
                    files.append({
                        'name': filename,
                        'url': file_url,
                        'size': obj['Size'],
                        'modified': obj['LastModified'].isoformat(),
                        'type': 'file'
                    })
        
        # Ordenar pastas e arquivos
        folders.sort(key=lambda x: x['name'])
        files.sort(key=lambda x: x['name'])
        
        return JsonResponse({
            'folders': folders,
            'files': files,
            'current_path': current_path,
            'parent_path': '/'.join(current_path.split('/')[:-1]) if current_path and '/' in current_path else None
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


# ─── Páginas do Conselho Nacional ───────────────────────────────────────────

class FaleConoscoView(TemplateView):
    template_name = 'blog/fale_conosco.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ContatoForm()
        context['page_title'] = 'Fale Conosco'
        return context

    def post(self, request, *args, **kwargs):
        form = ContatoForm(request.POST)
        if form.is_valid():
            nome = form.cleaned_data['nome']
            email = form.cleaned_data['email']
            assunto = form.cleaned_data.get('assunto') or 'Contato via site'
            mensagem = form.cleaned_data['mensagem']
            corpo = f"Nome: {nome}\nE-mail: {email}\n\n{mensagem}"
            try:
                send_mail(
                    subject=f"[ECC Nacional] {assunto}",
                    message=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_INFO['email']],
                    reply_to=[email],
                    fail_silently=False,
                )
                messages.success(request, 'Mensagem enviada com sucesso! Entraremos em contato em breve.')
            except Exception:
                messages.error(request, 'Ocorreu um erro ao enviar sua mensagem. Por favor, tente novamente.')
            return redirect('blog:fale_conosco')
        return render(request, self.template_name, {'form': form, 'page_title': 'Fale Conosco'})


class EstruturaDirecaoView(TemplateView):
    template_name = 'blog/estrutura.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Estrutura de Direção'
        return context


class SecretariaNacionalView(TemplateView):
    template_name = 'blog/secretaria.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Secretaria Nacional'
        return context


class RegionaisView(TemplateView):
    template_name = 'blog/regionais.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Regionais do ECC'
        return context


def regional_ajax(request, regional_id):
    """Retorna os dados de uma regional via AJAX para o mapa interativo."""
    regional = get_object_or_404(Regional, regional_id=regional_id)
    html = render(request, 'blog/partials/regional_card.html', {'regional': regional})
    return html


class EstatisticasView(ListView):
    model = Estatistica
    template_name = 'blog/estatisticas.html'
    context_object_name = 'estatisticas'
    ordering = ['-ano']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Estatísticas'
        return context


# ─── Admin CRUD para Estatísticas e Regionais ────────────────────────────────

class EstatisticaCreateView(AdminRequiredMixin, CreateView):
    model = Estatistica
    form_class = EstatisticaForm
    template_name = 'blog/admin/estatistica_form.html'
    success_url = reverse_lazy('blog:estatisticas')

    def form_valid(self, form):
        messages.success(self.request, 'Estatística criada com sucesso!')
        return super().form_valid(form)


class EstatisticaUpdateView(AdminRequiredMixin, UpdateView):
    model = Estatistica
    form_class = EstatisticaForm
    template_name = 'blog/admin/estatistica_form.html'
    success_url = reverse_lazy('blog:estatisticas')

    def form_valid(self, form):
        messages.success(self.request, 'Estatística atualizada com sucesso!')
        return super().form_valid(form)


class EstatisticaDeleteView(AdminRequiredMixin, DeleteView):
    model = Estatistica
    template_name = 'blog/admin/estatistica_confirm_delete.html'
    success_url = reverse_lazy('blog:estatisticas')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Estatística excluída com sucesso!')
        return super().delete(request, *args, **kwargs)


class RegionalCreateView(AdminRequiredMixin, CreateView):
    model = Regional
    form_class = RegionalForm
    template_name = 'blog/admin/regional_form.html'
    success_url = reverse_lazy('blog:regionais')

    def form_valid(self, form):
        messages.success(self.request, 'Regional criada com sucesso!')
        return super().form_valid(form)


class RegionalUpdateView(AdminRequiredMixin, UpdateView):
    model = Regional
    form_class = RegionalForm
    template_name = 'blog/admin/regional_form.html'
    success_url = reverse_lazy('blog:regionais')

    def form_valid(self, form):
        messages.success(self.request, 'Regional atualizada com sucesso!')
        return super().form_valid(form)
