from django.db import models
from unidades.models import Unidade


class DadoBancario(models.Model):
    banco = models.CharField(max_length=255, null=True, blank=True)
    agencia = models.CharField(max_length=255, null=True, blank=True)
    conta = models.CharField(max_length=255, null=True, blank=True)
    pix = models.CharField(max_length=255, null=True, blank=True)
    cnpj = models.CharField(max_length=18, null=True, blank=True)
    unidade = models.ForeignKey(Unidade, null=True, blank=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Dados bancários - {self.unidade}"

    class Meta:
        db_table = "dado_bancarios"
        verbose_name = "Dado Bancário"
        verbose_name_plural = "Dados Bancários"
