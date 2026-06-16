from django.contrib import admin
from .models import Noticia, Estatistica, Regional, ColaboradorNoticia, TokenAcesso


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'especial', 'ativa', 'autor', 'data_criacao')
    list_filter = ('especial', 'ativa', 'data_criacao', 'autor')
    search_fields = ('titulo', 'content')
    prepopulated_fields = {'slug': ('titulo',)}
    list_editable = ('especial', 'ativa')
    date_hierarchy = 'data_criacao'
    ordering = ('-data_criacao',)


@admin.register(Estatistica)
class EstatisticaAdmin(admin.ModelAdmin):
    list_display = ('ano', 'imagem', 'arquivo')
    ordering = ('-ano',)


@admin.register(Regional)
class RegionalAdmin(admin.ModelAdmin):
    list_display = ('nome', 'regional_id', 'casal', 'padre')
    search_fields = ('nome', 'casal', 'padre')
    ordering = ('nome',)


@admin.register(ColaboradorNoticia)
class ColaboradorNoticiaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'regiao', 'perfil', 'ativo', 'data_criacao')
    list_filter = ('perfil', 'ativo')
    search_fields = ('nome', 'email', 'regiao')
    list_editable = ('perfil', 'ativo')
    ordering = ('nome',)


@admin.register(TokenAcesso)
class TokenAcessoAdmin(admin.ModelAdmin):
    list_display = ('colaborador', 'token', 'criado_em', 'expira_em', 'usado')
    list_filter = ('usado', 'criado_em')
    search_fields = ('colaborador__nome', 'colaborador__email')
    readonly_fields = ('token', 'criado_em')
    ordering = ('-criado_em',)
