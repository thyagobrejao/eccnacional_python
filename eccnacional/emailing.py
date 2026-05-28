import logging
from decimal import Decimal
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from unidades.models import Unidade, UserUnidade

logger = logging.getLogger(__name__)


def build_portal_url(path: str = "/gestao/") -> str:
    base_url = getattr(settings, "APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/") + "/"
    return urljoin(base_url, path.lstrip("/"))


def _recipient_name(user) -> str:
    full_name = user.get_full_name().strip()
    return full_name or user.first_name or user.username or user.email


def _pedido_items(pedido):
    return pedido.pedidomaterial_set.select_related("material").all()


def _pedido_total(pedido) -> Decimal:
    total = Decimal("0.00")
    for item in _pedido_items(pedido):
        total += (item.valor_venda or Decimal("0.00")) * item.quantidade
    return total


def _active_unit_users(unidade):
    if not unidade:
        return []
    links = (
        UserUnidade.objects.filter(unidade=unidade, status=True, user__is_active=True)
        .select_related("user")
        .distinct()
    )
    return [link.user for link in links if link.user.email]


def send_templated_email(
    *,
    subject: str,
    to_emails: list[str],
    text_template: str,
    html_template: str | None,
    context: dict,
    reply_to: list[str] | None = None,
) -> int:
    if not to_emails:
        return 0

    text_body = render_to_string(text_template, context)
    email = EmailMultiAlternatives(
        subject=subject.strip(),
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to_emails,
        reply_to=reply_to or [],
    )

    if html_template:
        html_body = render_to_string(html_template, context)
        email.attach_alternative(html_body, "text/html")

    try:
        return email.send(fail_silently=False)
    except Exception:
        logger.exception("Falha ao enviar email '%s' para %s", subject, to_emails)
        return 0


def send_welcome_email(user, password, unidade) -> int:
    context = {
        "recipient_name": _recipient_name(user),
        "user": user,
        "password": password,
        "unidade": unidade,
        "portal_login_url": build_portal_url(settings.LOGIN_URL),
        "portal_home_url": build_portal_url("/gestao/"),
    }
    return send_templated_email(
        subject="Sua conta no ECC Nacional foi criada",
        to_emails=[user.email],
        text_template="emails/welcome_user.txt",
        html_template="emails/welcome_user.html",
        context=context,
    )


def send_new_order_notifications(pedido) -> int:
    unidade = pedido.unidade
    requester_emails = [user.email for user in _active_unit_users(unidade)]
    total_sent = 0
    items = _pedido_items(pedido)
    detail_url = build_portal_url(reverse("pedidos:detail", kwargs={"pk": pedido.pk}))

    base_context = {
        "pedido": pedido,
        "pedido_items": items,
        "pedido_total": _pedido_total(pedido),
        "detail_url": detail_url,
        "portal_home_url": build_portal_url("/gestao/"),
    }

    if unidade.tipo <= Unidade.Tipo.SETORIAL and settings.PEDIDOS_GRAFICA_EMAIL:
        total_sent += send_templated_email(
            subject=f"Novo Pedido de Material #{pedido.pk} - ECC Nacional",
            to_emails=[settings.PEDIDOS_GRAFICA_EMAIL],
            text_template="emails/new_order.txt",
            html_template="emails/new_order.html",
            context={**base_context, "recipient_name": "Gráfica"},
            reply_to=requester_emails,
        )
        return total_sent

    parent_users = _active_unit_users(unidade.parent)
    for user in parent_users:
        total_sent += send_templated_email(
            subject=f"Novo Pedido de Material #{pedido.pk} - ECC Nacional",
            to_emails=[user.email],
            text_template="emails/new_order.txt",
            html_template="emails/new_order.html",
            context={**base_context, "recipient_name": _recipient_name(user)},
        )
    return total_sent


def send_stock_notifications(pedido, movement_label: str) -> int:
    items = _pedido_items(pedido)
    detail_url = build_portal_url(reverse("pedidos:detail", kwargs={"pk": pedido.pk}))
    total_sent = 0

    targets = [
        (pedido.unidade, "Entrada" if movement_label == "Entrada" else movement_label),
        (pedido.unidade.parent, "Saída" if movement_label == "Entrada" else movement_label),
    ]

    for unidade, movement in targets:
        for user in _active_unit_users(unidade):
            total_sent += send_templated_email(
                subject=f"Estoque Atualizado - Pedido #{pedido.pk}",
                to_emails=[user.email],
                text_template="emails/stock_update.txt",
                html_template="emails/stock_update.html",
                context={
                    "recipient_name": _recipient_name(user),
                    "pedido": pedido,
                    "pedido_items": items,
                    "movement_label": movement,
                    "detail_url": detail_url,
                    "portal_home_url": build_portal_url("/gestao/"),
                },
            )
    return total_sent


def send_payment_confirmation_notifications(pedido) -> int:
    items = _pedido_items(pedido)
    detail_url = build_portal_url(reverse("pedidos:detail", kwargs={"pk": pedido.pk}))
    total_sent = 0

    for user in _active_unit_users(pedido.unidade):
        total_sent += send_templated_email(
            subject=f"Pagamento Confirmado - Pedido #{pedido.pk}",
            to_emails=[user.email],
            text_template="emails/payment_confirmed.txt",
            html_template="emails/payment_confirmed.html",
            context={
                "recipient_name": _recipient_name(user),
                "pedido": pedido,
                "pedido_items": items,
                "pedido_total": _pedido_total(pedido),
                "detail_url": detail_url,
                "portal_home_url": build_portal_url("/gestao/"),
            },
        )
    return total_sent