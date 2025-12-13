from django.db import models
from paroquias.models import Paroquia


class Casal(models.Model):
    ele = models.CharField(max_length=255, db_index=True)
    ela = models.CharField(max_length=255, db_index=True)
    email_ele = models.EmailField(null=True, blank=True, db_index=True)
    email_ela = models.EmailField(null=True, blank=True, db_index=True)
    telefone_ele = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    telefone_ela = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    obs = models.TextField(null=True, blank=True)
    foto = models.ImageField(upload_to="casais/", null=True, blank=True)
    paroquia = models.ForeignKey(
        Paroquia, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "casals"
        verbose_name = "Casal"
        verbose_name_plural = "Casais"

    def __str__(self) -> str:
        return f"{self.ele} e {self.ela}"
