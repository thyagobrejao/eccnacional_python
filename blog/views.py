from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, CreateView, UpdateView, DeleteView, ListView, DetailView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.conf import settings
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
from django.views import View
import uuid
import os
import re
from .models import Noticia, Estatistica, Regional, ColaboradorNoticia, TokenAcesso
from .forms import (
    NoticiaForm, ContatoForm, EstatisticaForm, RegionalForm,
    LoginMagicLinkForm, ColaboradorNoticiaForm, NoticiaColaboradorForm,
)


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


ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


@login_required
@require_POST
def tinymce_upload(request):
    """View para upload de imagens do TinyMCE para S3"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acesso negado'}, status=403)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'error': 'Nenhum arquivo enviado'}, status=400)

    if uploaded_file.content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse({'error': 'Tipo de arquivo não permitido. Envie apenas imagens.'}, status=400)

    if uploaded_file.size > MAX_UPLOAD_SIZE:
        return JsonResponse({'error': 'Arquivo muito grande. Máximo: 10 MB'}, status=400)

    try:
        from datetime import datetime

        environment = getattr(settings, 'ENVIRONMENT', 'development')
        now = datetime.now()

        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        unique_filename = f"{environment}/tinymce/{now:%Y}/{now:%m}/{now:%d}/{uuid.uuid4()}{file_extension}"

        file_path = default_storage.save(unique_filename, uploaded_file)
        file_url = default_storage.url(file_path)

        return JsonResponse({'location': file_url})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def tinymce_file_browser_view(request):
    """View para exibir o navegador de arquivos do TinyMCE"""
    return render(request, 'blog/admin/tinymce_file_browser.html')


@login_required
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
                EmailMessage(
                    subject=f"[ECC Nacional] {assunto}",
                    body=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[settings.CONTACT_FORM_RECIPIENT_EMAIL],
                    reply_to=[email],
                ).send(fail_silently=False)
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


# ═══════════════════════════════════════════════════════════════════════════════
# Sistema de Envio de Notícias por Colaboradores (Magic Link)
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Mixins de Acesso ────────────────────────────────────────────────────────

class ColaboradorRequiredMixin:
    """Verifica se o colaborador está autenticado via sessão."""

    def dispatch(self, request, *args, **kwargs):
        colaborador_id = request.session.get('colaborador_id')
        sessao_expira = request.session.get('colaborador_sessao_expira')

        if not colaborador_id or not sessao_expira:
            messages.warning(request, 'Você precisa fazer login para acessar esta página.')
            return redirect('blog:colaborador_login')

        # Verificar expiração da sessão (24h)
        from datetime import datetime
        try:
            expira = datetime.fromisoformat(sessao_expira)
            if timezone.now() > timezone.make_aware(expira) if timezone.is_naive(expira) else timezone.now() > expira:
                # Limpar sessão expirada
                request.session.flush()
                messages.warning(request, 'Sua sessão expirou. Faça login novamente.')
                return redirect('blog:colaborador_login')
        except (ValueError, TypeError):
            request.session.flush()
            return redirect('blog:colaborador_login')

        try:
            request.colaborador = ColaboradorNoticia.objects.get(pk=colaborador_id, ativo=True)
        except ColaboradorNoticia.DoesNotExist:
            request.session.flush()
            messages.error(request, 'Colaborador não encontrado ou desativado.')
            return redirect('blog:colaborador_login')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['colaborador'] = self.request.colaborador
        return context


class RevisorRequiredMixin(ColaboradorRequiredMixin):
    """Verifica se o colaborador é um revisor."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        # Se o super já redirecionou (login), retorna
        if hasattr(response, 'status_code') and response.status_code in (301, 302):
            return response
        if not request.colaborador.is_revisor:
            messages.error(request, 'Acesso restrito a revisores.')
            return redirect('blog:colaborador_painel')
        return response


# ─── Autenticação por Magic Link ─────────────────────────────────────────────

class LoginMagicLinkView(View):
    """Exibe formulário de e-mail e envia o magic link."""

    def get(self, request):
        # Se já está logado, redirecionar ao painel
        if request.session.get('colaborador_id'):
            return redirect('blog:colaborador_painel')
        form = LoginMagicLinkForm()
        return render(request, 'blog/noticias/login.html', {'form': form})

    def post(self, request):
        form = LoginMagicLinkForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                colaborador = ColaboradorNoticia.objects.get(email__iexact=email, ativo=True)
            except ColaboradorNoticia.DoesNotExist:
                # Por segurança, não revelamos se o e-mail existe ou não
                messages.success(
                    request,
                    'Se o e-mail informado estiver cadastrado, você receberá um link de acesso em instantes.'
                )
                return redirect('blog:colaborador_link_enviado')

            # Criar token de acesso
            token_obj = TokenAcesso(colaborador=colaborador)
            token_obj.expira_em = timezone.now() + timedelta(hours=1)
            token_obj.save()

            # Construir URL do magic link
            link = request.build_absolute_uri(
                reverse('blog:colaborador_verificar', kwargs={'token': str(token_obj.token)})
            )

            # Enviar e-mail
            context = {
                'colaborador': colaborador,
                'link': link,
                'validade': '1 hora',
                'portal_home_url': getattr(settings, 'APP_BASE_URL', request.build_absolute_uri('/')),
            }
            text_content = render_to_string('emails/magic_link.txt', context)
            html_content = render_to_string('emails/magic_link.html', context)

            msg = EmailMultiAlternatives(
                subject='[ECC Nacional] Seu link de acesso ao painel de notícias',
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[colaborador.email],
            )
            msg.attach_alternative(html_content, 'text/html')
            msg.send(fail_silently=False)

            messages.success(
                request,
                'Se o e-mail informado estiver cadastrado, você receberá um link de acesso em instantes.'
            )
            return redirect('blog:colaborador_link_enviado')

        return render(request, 'blog/noticias/login.html', {'form': form})


class LinkEnviadoView(TemplateView):
    """Página de confirmação após solicitar o link."""
    template_name = 'blog/noticias/link_enviado.html'


class ValidarTokenView(View):
    """Valida o token do magic link, cria sessão de 24h."""

    def get(self, request, token):
        try:
            token_obj = TokenAcesso.objects.select_related('colaborador').get(token=token)
        except TokenAcesso.DoesNotExist:
            messages.error(request, 'Link de acesso inválido.')
            return redirect('blog:colaborador_login')

        if not token_obj.is_valido:
            messages.error(request, 'Este link de acesso já foi utilizado ou expirou. Solicite um novo.')
            return redirect('blog:colaborador_login')

        if not token_obj.colaborador.ativo:
            messages.error(request, 'Sua conta está desativada. Entre em contato com um revisor.')
            return redirect('blog:colaborador_login')

        # Marcar token como usado
        token_obj.usado = True
        token_obj.save(update_fields=['usado'])

        # Criar sessão do colaborador (24h)
        request.session['colaborador_id'] = token_obj.colaborador.pk
        request.session['colaborador_nome'] = token_obj.colaborador.nome
        request.session['colaborador_perfil'] = token_obj.colaborador.perfil
        sessao_expira = timezone.now() + timedelta(hours=24)
        request.session['colaborador_sessao_expira'] = sessao_expira.isoformat()

        messages.success(request, f'Bem-vindo(a), {token_obj.colaborador.nome}!')
        return redirect('blog:colaborador_painel')


class LogoutColaboradorView(View):
    """Encerra a sessão do colaborador."""

    def get(self, request):
        keys_to_clear = [
            'colaborador_id', 'colaborador_nome',
            'colaborador_perfil', 'colaborador_sessao_expira',
        ]
        for key in keys_to_clear:
            request.session.pop(key, None)
        messages.success(request, 'Você saiu do painel de notícias.')
        return redirect('blog:colaborador_login')


# ─── Painel de Notícias do Colaborador ───────────────────────────────────────

class PainelNoticiasView(ColaboradorRequiredMixin, TemplateView):
    """Painel principal: lista notícias do colaborador (ou todas, se revisor)."""
    template_name = 'blog/noticias/painel.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        colaborador = self.request.colaborador

        if colaborador.is_revisor:
            noticias = Noticia.objects.filter(autor__isnull=False).order_by('-data_criacao')
        else:
            noticias = Noticia.objects.filter(autor=colaborador).order_by('-data_criacao')

        paginator = Paginator(noticias, 10)
        page_number = self.request.GET.get('page')
        context['noticias'] = paginator.get_page(page_number)
        context['page_title'] = 'Painel de Notícias'
        return context


class NoticiaColaboradorCreateView(ColaboradorRequiredMixin, CreateView):
    """Criar nova notícia como colaborador."""
    model = Noticia
    form_class = NoticiaColaboradorForm
    template_name = 'blog/noticias/noticia_form.html'
    success_url = reverse_lazy('blog:colaborador_painel')

    def form_valid(self, form):
        form.instance.autor = self.request.colaborador
        # Editores criam notícias inativas (rascunho); Revisores criam ativas
        form.instance.ativa = self.request.colaborador.is_revisor
        messages.success(
            self.request,
            'Notícia criada com sucesso!'
            + ('' if self.request.colaborador.is_revisor
               else ' Ela será publicada após revisão.')
        )
        return super().form_valid(form)


class NoticiaColaboradorDetailView(ColaboradorRequiredMixin, DetailView):
    """Visualização detalhada (preview) da notícia no painel do colaborador."""
    model = Noticia
    template_name = 'blog/noticias/noticia_detail.html'
    context_object_name = 'noticia'

    def get_queryset(self):
        colaborador = self.request.colaborador
        if colaborador.is_revisor:
            return Noticia.objects.filter(autor__isnull=False)
        return Noticia.objects.filter(autor=colaborador)


class NoticiaColaboradorUpdateView(ColaboradorRequiredMixin, UpdateView):
    """Editar notícia existente."""
    model = Noticia
    form_class = NoticiaColaboradorForm
    template_name = 'blog/noticias/noticia_form.html'
    success_url = reverse_lazy('blog:colaborador_painel')

    def get_queryset(self):
        colaborador = self.request.colaborador
        if colaborador.is_revisor:
            return Noticia.objects.filter(autor__isnull=False)
        return Noticia.objects.filter(autor=colaborador)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not request.colaborador.is_revisor and self.object.ativa:
            messages.error(request, 'Você não pode alterar uma notícia que já foi publicada.')
            return redirect('blog:colaborador_noticia_detail', pk=self.object.pk)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not request.colaborador.is_revisor and self.object.ativa:
            messages.error(request, 'Você não pode alterar uma notícia que já foi publicada.')
            return redirect('blog:colaborador_noticia_detail', pk=self.object.pk)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Notícia atualizada com sucesso!')
        return super().form_valid(form)


class PublicarNoticiaView(RevisorRequiredMixin, View):
    """Revisor ativa ou desativa uma notícia (toggle)."""

    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk, autor__isnull=False)
        noticia.ativa = not noticia.ativa
        noticia.save(update_fields=['ativa'])
        status = 'publicada' if noticia.ativa else 'despublicada'
        messages.success(request, f'Notícia "{noticia.titulo}" {status} com sucesso!')
        return redirect('blog:colaborador_noticia_detail', pk=noticia.pk)

    def get(self, request, pk):
        return self.post(request, pk)


# ─── Gestão de Colaboradores (Revisor) ───────────────────────────────────────

class ColaboradorListView(RevisorRequiredMixin, TemplateView):
    """Lista todos os colaboradores cadastrados."""
    template_name = 'blog/noticias/colaborador_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['colaboradores'] = ColaboradorNoticia.objects.all()
        context['page_title'] = 'Colaboradores'
        return context


class ColaboradorCreateView(RevisorRequiredMixin, CreateView):
    """Cadastrar novo colaborador."""
    model = ColaboradorNoticia
    form_class = ColaboradorNoticiaForm
    template_name = 'blog/noticias/colaborador_form.html'
    success_url = reverse_lazy('blog:colaborador_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Novo Colaborador'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Colaborador cadastrado com sucesso!')
        return super().form_valid(form)


class ColaboradorUpdateView(RevisorRequiredMixin, UpdateView):
    """Editar colaborador existente."""
    model = ColaboradorNoticia
    form_class = ColaboradorNoticiaForm
    template_name = 'blog/noticias/colaborador_form.html'
    success_url = reverse_lazy('blog:colaborador_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Editar Colaborador'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Colaborador atualizado com sucesso!')
        return super().form_valid(form)


# ─── Upload de imagens para TinyMCE (colaboradores) ─────────────────────────

def colaborador_tinymce_upload(request):
    """Upload de imagens do TinyMCE para colaboradores autenticados por sessão."""
    colaborador_id = request.session.get('colaborador_id')
    if not colaborador_id:
        return JsonResponse({'error': 'Acesso negado'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'error': 'Nenhum arquivo enviado'}, status=400)

    if uploaded_file.content_type not in ALLOWED_IMAGE_TYPES:
        return JsonResponse({'error': 'Tipo de arquivo não permitido. Envie apenas imagens.'}, status=400)

    if uploaded_file.size > MAX_UPLOAD_SIZE:
        return JsonResponse({'error': 'Arquivo muito grande. Máximo: 10 MB'}, status=400)

    try:
        from datetime import datetime as dt
        environment = getattr(settings, 'ENVIRONMENT', 'development')
        now = dt.now()
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        unique_filename = f"{environment}/tinymce/{now:%Y}/{now:%m}/{now:%d}/{uuid.uuid4()}{file_extension}"
        file_path = default_storage.save(unique_filename, uploaded_file)
        file_url = default_storage.url(file_path)
        return JsonResponse({'location': file_url})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
