from django.contrib import admin
from .models import Noticia


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'especial', 'ativa', 'data_criacao')
    list_filter = ('especial', 'ativa', 'data_criacao')
    search_fields = ('titulo', 'content')
    prepopulated_fields = {'slug': ('titulo',)}
    list_editable = ('especial', 'ativa')
    date_hierarchy = 'data_criacao'
    ordering = ('-data_criacao',)
