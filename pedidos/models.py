from django.db import models
from unidades.models import Unidade
from municipios.models import Cidade
from materiais.models import Material


class Pedido(models.Model):
    class Status(models.IntegerChoices):
        NOVO = 0, "Novo"
        RECEBIDO = 1, "Recebido"
        REALIZADO = 2, "Realizado"
        CANCELADO = 3, "Cancelado"

    status = models.PositiveSmallIntegerField(
        choices=Status.choices, default=Status.NOVO, db_index=True
    )
    solicitante = models.CharField(max_length=255, db_index=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    cep = models.CharField(max_length=20, null=True, blank=True)
    telefones = models.CharField(max_length=255, null=True, blank=True)
    codigo_correios = models.CharField(max_length=255, null=True, blank=True)
    obs = models.TextField(null=True, blank=True)
    unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE)
    cidade = models.ForeignKey(Cidade, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    materiais = models.ManyToManyField(
        Material, through="PedidoMaterial", related_name="pedidos"
    )

    class Meta:
        db_table = "pedidos"
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self) -> str:
        return f"Pedido #{self.id} - {self.solicitante}"


class PedidoMaterial(models.Model):
    quantidade = models.PositiveIntegerField()
    valor_venda = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pedido_material"
        unique_together = ("pedido", "material")

    def __str__(self) -> str:
        return f"{self.material} x {self.quantidade} (Pedido #{self.pedido_id})"
