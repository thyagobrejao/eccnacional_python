from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class Unidade(models.Model):
    class Tipo(models.IntegerChoices):
        ROOT = 0, "Root"
        NACIONAL = 1, "Nacional"
        REGIONAL = 2, "Regional"
        DIOCESANO = 3, "Diocesano"
        SETORIAL = 4, "Setorial"
        PAROQUIA = 5, "Paróquia"

    nome = models.CharField(max_length=255, db_index=True)
    digito = models.DecimalField(
        max_digits=5, decimal_places=0, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    vencimento = models.PositiveIntegerField(default=40)
    bloqueado = models.BooleanField(default=False)
    tipo = models.PositiveSmallIntegerField(choices=Tipo.choices)
    status = models.BooleanField(default=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Many-to-many with User through UserUnidade
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, through="UserUnidade", related_name="unidades")

    def __str__(self) -> str:
        return self.nome

    class Meta:
        db_table = "unidades"


class UserUnidade(models.Model):
    status = models.BooleanField(default=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_unidade"

    def __str__(self) -> str:
        return f"{self.user} - {self.unidade} ({'Ativo' if self.status else 'Inativo'})"
