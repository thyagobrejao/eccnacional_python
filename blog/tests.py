from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class FaleConoscoViewTests(TestCase):
	@override_settings(
		DEFAULT_FROM_EMAIL="noreply@eccnacional.com.br",
		CONTACT_FORM_RECIPIENT_EMAIL="admin@eccnacional.com.br",
	)
	def test_contact_form_sends_email_to_admin_recipient(self):
		response = self.client.post(
			reverse("blog:fale_conosco"),
			{
				"nome": "Joao da Silva",
				"email": "joao@example.com",
				"assunto": "Dvida",
				"mensagem": "Preciso de ajuda com o cadastro.",
			},
		)

		self.assertRedirects(response, reverse("blog:fale_conosco"))
		self.assertEqual(len(mail.outbox), 1)

		message = mail.outbox[0]
		self.assertEqual(message.to, ["admin@eccnacional.com.br"])
		self.assertEqual(message.reply_to, ["joao@example.com"])
		self.assertEqual(message.from_email, "noreply@eccnacional.com.br")
