from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from materiais.models import Material, UnidadeMaterial
from municipios.models import Cidade
from pedidos.models import Pedido
from unidades.models import Unidade, UserUnidade


class PedidoViewsTests(TestCase):
	def setUp(self):
		self.user_model = get_user_model()
		self.cidade = Cidade.objects.create(nome="São Paulo", uf="SP")

		self.unidade_recebedora = Unidade.objects.create(
			nome="Regional SP",
			tipo=Unidade.Tipo.REGIONAL,
			digito=7,
		)
		self.unidade_solicitante = Unidade.objects.create(
			nome="Diocesano Centro",
			tipo=Unidade.Tipo.DIOCESANO,
			parent=self.unidade_recebedora,
			digito=3,
		)
		self.unidade_neta = Unidade.objects.create(
			nome="Setorial Centro",
			tipo=Unidade.Tipo.SETORIAL,
			parent=self.unidade_solicitante,
			digito=2,
		)
		self.outra_unidade = Unidade.objects.create(
			nome="Regional Sul",
			tipo=Unidade.Tipo.REGIONAL,
			digito=9,
		)
		self.outra_solicitante = Unidade.objects.create(
			nome="Diocesano Sul",
			tipo=Unidade.Tipo.DIOCESANO,
			parent=self.outra_unidade,
			digito=4,
		)

		self.receiver_user = self.user_model.objects.create_user(
			username="receiver",
			email="receiver@example.com",
			password="secret123",
		)
		UserUnidade.objects.create(
			user=self.receiver_user,
			unidade=self.unidade_recebedora,
			status=True,
		)

		self.requester_user = self.user_model.objects.create_user(
			username="requester",
			email="requester@example.com",
			password="secret123",
		)
		UserUnidade.objects.create(
			user=self.requester_user,
			unidade=self.unidade_solicitante,
			status=True,
		)

		self.grandchild_user = self.user_model.objects.create_user(
			username="grandchild",
			email="grandchild@example.com",
			password="secret123",
		)
		UserUnidade.objects.create(
			user=self.grandchild_user,
			unidade=self.unidade_neta,
			status=True,
		)

		self.material = Material.objects.create(descricao="Livro")
		UnidadeMaterial.objects.create(
			unidade=self.unidade_recebedora,
			material=self.material,
			quantidade=100,
			valor="12.50",
		)

	def create_pedido(self, unidade, solicitante="Fulano"):
		pedido = Pedido.objects.create(
			solicitante=solicitante,
			unidade=unidade,
			cidade=self.cidade,
			endereco="Rua 1",
			cep="01000-000",
			telefones="(11) 99999-0000",
		)
		pedido.pedidomaterial_set.create(
			material=self.material,
			quantidade=2,
			valor_venda="12.50",
		)
		return pedido

	def build_create_payload(self, unidade=None, valor_venda="12.50", **extra):
		payload = {
			"solicitante": "João da Silva",
			"unidade": str((unidade or self.unidade_solicitante).pk),
			"cidade": str(self.cidade.pk),
			"endereco": "Rua das Flores, 100",
			"cep": "01000-000",
			"telefones": "(11) 99999-0000",
			"obs": "Entregar com atenção",
			"pedidomaterial_set-TOTAL_FORMS": "1",
			"pedidomaterial_set-INITIAL_FORMS": "0",
			"pedidomaterial_set-MIN_NUM_FORMS": "1",
			"pedidomaterial_set-MAX_NUM_FORMS": "1000",
			"pedidomaterial_set-0-material": str(self.material.pk),
			"pedidomaterial_set-0-quantidade": "2",
			"pedidomaterial_set-0-valor_venda": valor_venda,
		}
		payload.update(extra)
		return payload

	def test_recebidos_lista_apenas_pedidos_do_nivel_imediatamente_inferior(self):
		pedido_recebido = self.create_pedido(self.unidade_solicitante, solicitante="Pedido válido")
		self.create_pedido(self.unidade_neta, solicitante="Pedido neto")
		self.create_pedido(self.outra_solicitante, solicitante="Pedido outra regional")

		self.client.force_login(self.receiver_user)
		response = self.client.get(reverse("pedidos:recebidos"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, pedido_recebido.solicitante)
		self.assertNotContains(response, "Pedido neto")
		self.assertNotContains(response, "Pedido outra regional")

	def test_detail_exibe_atualizacao_de_status_so_para_unidade_recebedora(self):
		pedido = self.create_pedido(self.unidade_solicitante)
		detail_url = reverse("pedidos:detail", kwargs={"pk": pedido.pk})

		self.client.force_login(self.requester_user)
		requester_response = self.client.get(detail_url)
		self.assertEqual(requester_response.status_code, 200)
		self.assertNotContains(requester_response, "Alterar Status")

		self.client.force_login(self.receiver_user)
		receiver_response = self.client.get(detail_url)
		self.assertEqual(receiver_response.status_code, 200)
		self.assertContains(receiver_response, "Alterar Status")

	def test_update_status_rejeita_usuario_da_unidade_solicitante(self):
		pedido = self.create_pedido(self.unidade_solicitante)

		self.client.force_login(self.requester_user)
		response = self.client.post(
			reverse("pedidos:update_status", kwargs={"pk": pedido.pk}),
			{"status": str(Pedido.Status.RECEBIDO)},
			follow=True,
		)

		pedido.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertEqual(pedido.status, Pedido.Status.NOVO)
		self.assertContains(
			response,
			"Apenas a unidade que recebeu o pedido pode atualizar o status.",
		)

	def test_create_post_exibe_conferencia_antes_de_salvar(self):
		payload = self.build_create_payload()

		self.client.force_login(self.requester_user)
		response = self.client.post(reverse("pedidos:novo"), payload)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Confirme o pedido")
		self.assertEqual(Pedido.objects.count(), 0)

	def test_create_confirm_salva_pedido_apos_conferencia(self):
		payload = self.build_create_payload(submission_step="confirm")

		self.client.force_login(self.requester_user)
		response = self.client.post(reverse("pedidos:novo"), payload)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(Pedido.objects.count(), 1)

	def test_api_materiais_ignora_preco_de_avo_e_usa_so_pai_imediato(self):
		self.client.force_login(self.grandchild_user)
		response = self.client.get(
			reverse("pedidos:api_materiais"),
			{"unidade_id": self.unidade_neta.pk},
		)

		self.assertEqual(response.status_code, 200)
		materiais = response.json()["materiais"]
		material_data = next(item for item in materiais if item["id"] == self.material.pk)
		self.assertEqual(material_data["preco"], 0.0)
		self.assertIsNone(material_data["unidade_origem"])

	def test_api_materiais_retorna_preco_da_unidade_pai_imediata(self):
		self.client.force_login(self.requester_user)
		response = self.client.get(
			reverse("pedidos:api_materiais"),
			{"unidade_id": self.unidade_solicitante.pk},
		)

		self.assertEqual(response.status_code, 200)
		materiais = response.json()["materiais"]
		material_data = next(item for item in materiais if item["id"] == self.material.pk)
		self.assertEqual(material_data["preco"], 12.5)
		self.assertEqual(material_data["unidade_origem"], self.unidade_recebedora.nome)

	def test_novo_pedido_carrega_precos_iniciais_da_unidade_pai(self):
		self.client.force_login(self.requester_user)
		response = self.client.get(reverse("pedidos:novo"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '"%s": 12.5' % self.material.pk)

	def test_create_preview_usa_preco_apenas_da_unidade_pai_imediata(self):
		payload = self.build_create_payload(unidade=self.unidade_neta, valor_venda="12.50")

		self.client.force_login(self.grandchild_user)
		response = self.client.post(reverse("pedidos:novo"), payload)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(Pedido.objects.count(), 0)
		self.assertEqual(
			response.context["pedido_items_preview"][0]["valor_venda"],
			Decimal("0.00"),
		)
