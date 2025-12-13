from django.db import models
from municipios.models import Cidade
from unidades.models import Unidade


class Paroquia(models.Model):
    nome = models.CharField(max_length=255, db_index=True)
    bairro = models.CharField(max_length=255, null=True, blank=True)
    cidade = models.ForeignKey(Cidade, on_delete=models.CASCADE)
    unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "paroquias"
        verbose_name = "Paróquia"
        verbose_name_plural = "Paróquias"

    def __str__(self) -> str:
        return self.nome
