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
