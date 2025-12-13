from django.db import models
from unidades.models import Unidade
from casais.models import Casal
from paroquias.models import Paroquia
from equipes.models import Equipe


class Encontro(models.Model):
    nome = models.CharField(max_length=255, null=True, blank=True, db_index=True, default="S/N")
    etapa = models.PositiveSmallIntegerField()
    data = models.DateField()
    quadrante = models.PositiveIntegerField(null=True, blank=True)
    unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE)
    paroquia = models.ForeignKey(Paroquia, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    casais = models.ManyToManyField(Casal, through="CasalEncontro", related_name="encontros")

    class Meta:
        db_table = "encontros"
        verbose_name = "Encontro"
        verbose_name_plural = "Encontros"

    def __str__(self) -> str:
        return f"{self.nome} ({self.data})"


class CasalEncontro(models.Model):
    casal = models.ForeignKey(Casal, on_delete=models.CASCADE)
    encontro = models.ForeignKey(Encontro, on_delete=models.CASCADE)
    equipe = models.ForeignKey(Equipe, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "casal_encontro"
        unique_together = ("casal", "encontro")

    def __str__(self) -> str:
        return f"{self.casal} @ {self.encontro}"
