from django.db import models
from unidades.models import Unidade


class Material(models.Model):
    descricao = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "materials"
        verbose_name = "Material"
        verbose_name_plural = "Materiais"

    def __str__(self) -> str:
        return self.descricao


class UnidadeMaterial(models.Model):
    quantidade = models.PositiveIntegerField(default=0)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "unidade_material"
        unique_together = ("unidade", "material")

    def __str__(self) -> str:
        return f"{self.unidade} - {self.material}: {self.quantidade}"
