from django.urls import path, include
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.BlogHomeView.as_view(), name='home'),
    path('conheca-o-ecc/', views.NoticiasEspeciaisView.as_view(), name='noticias_especiais'),
    path('noticia/<slug:slug>/', views.NoticiaDetailView.as_view(), name='noticia_detail'),
    
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