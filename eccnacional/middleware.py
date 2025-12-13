from django.shortcuts import redirect
from django.conf import settings


class GestaoAuthenticationMiddleware:
    """Middleware para exigir autenticação em todas as rotas /gestao/."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Verificar se a URL começa com /gestao/
        if request.path.startswith("/gestao/"):
            # Ignorar URL de login
            if request.path == "/gestao/login/":
                return self.get_response(request)

            # Redirecionar para login se não autenticado
            if not request.user.is_authenticated:
                login_url = getattr(settings, "LOGIN_URL", "/gestao/login/")
                return redirect(f"{login_url}?next={request.path}")

        return self.get_response(request)
