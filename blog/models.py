from django.db import models
from django.utils.text import slugify
from django.urls import reverse
from django_ckeditor_5.fields import CKEditor5Field
from django.conf import settings
from datetime import datetime
import uuid
import os


def noticia_image_upload_path(instance, filename):
    """Função para definir o caminho de upload das imagens principais das notícias"""
    # Obter o ambiente do sistema
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    
    # Obter data atual para criar estrutura de pastas ANO/MES/DIA
    now = datetime.now()
    year = now.strftime('%Y')
    month = now.strftime('%m')
    day = now.strftime('%d')
    
    # Gerar nome único para o arquivo
    file_extension = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    
    return f"{environment}/noticias/{year}/{month}/{day}/{unique_filename}"


class Noticia(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    content = CKEditor5Field(verbose_name="Conteúdo", config_name='news')
    imagem_principal = models.ImageField(
        upload_to=noticia_image_upload_path,
        blank=True,
        null=True,
        verbose_name="Imagem Principal",
        help_text="Imagem que será exibida como destaque da notícia"
    )
    especial = models.BooleanField(default=False, verbose_name="Notícia Especial")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")
    ativa = models.BooleanField(default=True, verbose_name="Ativa")
    
    class Meta:
        verbose_name = "Notícia"
        verbose_name_plural = "Notícias"
        ordering = ['-data_criacao']
    
    def __str__(self):
        return self.titulo
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.titulo)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('blog:noticia_detail', kwargs={'slug': self.slug})


def estatistica_imagem_upload_path(instance, filename):
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    ext = os.path.splitext(filename)[1]
    return f"{environment}/estatisticas/imagens/{uuid.uuid4()}{ext}"


def estatistica_arquivo_upload_path(instance, filename):
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    ext = os.path.splitext(filename)[1]
    return f"{environment}/estatisticas/arquivos/{uuid.uuid4()}{ext}"


class Estatistica(models.Model):
    ano = models.CharField(max_length=10, verbose_name="Ano")
    imagem = models.ImageField(
        upload_to=estatistica_imagem_upload_path,
        verbose_name="Imagem de Capa",
    )
    arquivo = models.FileField(
        upload_to=estatistica_arquivo_upload_path,
        verbose_name="Arquivo (PDF)",
    )

    class Meta:
        verbose_name = "Estatística"
        verbose_name_plural = "Estatísticas"
        ordering = ['-ano']

    def __str__(self):
        return f"Estatísticas {self.ano}"


def regional_imagem_upload_path(instance, filename):
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    ext = os.path.splitext(filename)[1]
    return f"{environment}/regionais/{uuid.uuid4()}{ext}"


class Regional(models.Model):
    REGIONAL_CHOICES = [
        ('noroeste', 'Noroeste'),
        ('norte1', 'Norte 1'),
        ('norte2', 'Norte 2'),
        ('norte3', 'Norte 3'),
        ('nordeste1', 'Nordeste 1'),
        ('nordeste2', 'Nordeste 2'),
        ('nordeste3', 'Nordeste 3'),
        ('nordeste4', 'Nordeste 4'),
        ('nordeste5', 'Nordeste 5'),
        ('centroOeste', 'Centro-Oeste'),
        ('oeste1', 'Oeste 1'),
        ('oeste2', 'Oeste 2'),
        ('leste1', 'Leste 1'),
        ('leste2', 'Leste 2'),
        ('leste3', 'Leste 3'),
        ('sul1', 'Sul 1'),
        ('sul2', 'Sul 2'),
        ('sul3', 'Sul 3'),
        ('sul4', 'Sul 4'),
    ]
    nome = models.CharField(max_length=100, verbose_name="Nome da Regional")
    regional_id = models.CharField(
        max_length=50, unique=True, choices=REGIONAL_CHOICES, verbose_name="ID da Regional"
    )
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    casal = models.CharField(max_length=200, blank=True, verbose_name="Casal Responsável")
    padre = models.CharField(max_length=200, blank=True, verbose_name="Padre / Assistente")
    imagem = models.ImageField(
        upload_to=regional_imagem_upload_path, blank=True, null=True, verbose_name="Imagem"
    )

    class Meta:
        verbose_name = "Regional"
        verbose_name_plural = "Regionais"
        ordering = ['nome']

    def __str__(self):
        return self.nome
