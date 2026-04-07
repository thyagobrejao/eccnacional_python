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
    path('admin/estatisticas/nova/', views.EstatisticaCreateView.as_view(), name='estatistica_create'),
    path('admin/estatisticas/<int:pk>/editar/', views.EstatisticaUpdateView.as_view(), name='estatistica_update'),
    path('admin/estatisticas/<int:pk>/excluir/', views.EstatisticaDeleteView.as_view(), name='estatistica_delete'),

    # Admin CRUD – Regionais
    path('admin/regionais/nova/', views.RegionalCreateView.as_view(), name='regional_create'),
    path('admin/regionais/<int:pk>/editar/', views.RegionalUpdateView.as_view(), name='regional_update'),

    # URLs de administração de notícias
    path('blog/admin/noticias/', views.NoticiaListView.as_view(), name='admin_noticia_list'),
    path('blog/admin/noticias/nova/', views.NoticiaCreateView.as_view(), name='admin_noticia_create'),
    path('blog/admin/noticias/<int:pk>/editar/', views.NoticiaUpdateView.as_view(), name='admin_noticia_update'),
    path('blog/admin/noticias/<int:pk>/excluir/', views.NoticiaDeleteView.as_view(), name='admin_noticia_delete'),

    # TinyMCE upload
    path('blog/tinymce/upload/', views.tinymce_upload, name='tinymce_upload'),
    path('blog/tinymce/browse/', views.tinymce_file_browser, name='tinymce_file_browser'),
    path('blog/tinymce/browser/', views.tinymce_file_browser_view, name='tinymce_file_browser_view'),
]