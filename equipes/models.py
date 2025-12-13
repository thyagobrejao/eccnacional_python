from django.db import models


class Equipe(models.Model):
    nome = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "equipes"
        verbose_name = "Equipe"
        verbose_name_plural = "Equipes"

    def __str__(self) -> str:
        return self.nome
