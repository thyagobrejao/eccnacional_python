from django.db import models


class Cidade(models.Model):
    nome = models.CharField(max_length=255, db_index=True)
    uf = models.CharField(max_length=2, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cidades"
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"

    def __str__(self) -> str:
        return f"{self.nome}/{self.uf}"
