from django.urls import path, include
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.BlogHomeView.as_view(), name='home'),
    path('conheca-o-ecc/', views.NoticiasEspeciaisView.as_view(), name='noticias_especiais'),
    path('noticia/<slug:slug>/', views.NoticiaDetailView.as_view(), name='noticia_detail'),

    # Páginas do Conselho Nacional
    path('fale-conosco/', views.FaleConoscoView.as_view(), name='fale_conosco'),
    path('estrutura-de-direcao/', views.EstruturaDirecaoView.as_view(), name='estrutura'),
    path('secretaria-nacional/', views.SecretariaNacionalView.as_view(), name='secretaria'),
    path('regionais/', views.RegionaisView.as_view(), name='regionais'),
    path('regionais/ajax/<str:regional_id>/', views.regional_ajax, name='regional_ajax'),
    path('estatisticas/', views.EstatisticasView.as_view(), name='estatisticas'),

    # Admin CRUD – Estatísticas
    path('gestao-blog/estatisticas/nova/', views.EstatisticaCreateView.as_view(), name='estatistica_create'),
    path('gestao-blog/estatisticas/<int:pk>/editar/', views.EstatisticaUpdateView.as_view(), name='estatistica_update'),
    path('gestao-blog/estatisticas/<int:pk>/excluir/', views.EstatisticaDeleteView.as_view(), name='estatistica_delete'),

    # Admin CRUD – Regionais
    path('gestao-blog/regionais/nova/', views.RegionalCreateView.as_view(), name='regional_create'),
    path('gestao-blog/regionais/<int:pk>/editar/', views.RegionalUpdateView.as_view(), name='regional_update'),

    # URLs de administração de notícias
    path('blog/admin/noticias/', views.NoticiaListView.as_view(), name='admin_noticia_list'),
    path('blog/admin/noticias/nova/', views.NoticiaCreateView.as_view(), name='admin_noticia_create'),
    path('blog/admin/noticias/<int:pk>/editar/', views.NoticiaUpdateView.as_view(), name='admin_noticia_update'),
    path('blog/admin/noticias/<int:pk>/excluir/', views.NoticiaDeleteView.as_view(), name='admin_noticia_delete'),

    # TinyMCE upload
    path('blog/tinymce/upload/', views.tinymce_upload, name='tinymce_upload'),
    path('blog/tinymce/browse/', views.tinymce_file_browser, name='tinymce_file_browser'),
    path('blog/tinymce/browser/', views.tinymce_file_browser_view, name='tinymce_file_browser_view'),

    # ─── Sistema de Colaboradores (Magic Link) ───────────────────────────────
    # Autenticação
    path('noticias/login/', views.LoginMagicLinkView.as_view(), name='colaborador_login'),
    path('noticias/link-enviado/', views.LinkEnviadoView.as_view(), name='colaborador_link_enviado'),
    path('noticias/verificar/<uuid:token>/', views.ValidarTokenView.as_view(), name='colaborador_verificar'),
    path('noticias/logout/', views.LogoutColaboradorView.as_view(), name='colaborador_logout'),

    # Painel de notícias do colaborador
    path('noticias/painel/', views.PainelNoticiasView.as_view(), name='colaborador_painel'),
    path('noticias/painel/nova/', views.NoticiaColaboradorCreateView.as_view(), name='colaborador_noticia_create'),
    path('noticias/painel/<int:pk>/', views.NoticiaColaboradorDetailView.as_view(), name='colaborador_noticia_detail'),
    path('noticias/painel/<int:pk>/editar/', views.NoticiaColaboradorUpdateView.as_view(), name='colaborador_noticia_update'),
    path('noticias/painel/<int:pk>/publicar/', views.PublicarNoticiaView.as_view(), name='colaborador_noticia_publicar'),

    # Gestão de colaboradores (Revisor)
    path('noticias/colaboradores/', views.ColaboradorListView.as_view(), name='colaborador_list'),
    path('noticias/colaboradores/novo/', views.ColaboradorCreateView.as_view(), name='colaborador_create'),
    path('noticias/colaboradores/<int:pk>/editar/', views.ColaboradorUpdateView.as_view(), name='colaborador_update'),

    # TinyMCE upload para colaboradores
    path('noticias/tinymce/upload/', views.colaborador_tinymce_upload, name='colaborador_tinymce_upload'),
]