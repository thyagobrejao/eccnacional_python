from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Autentica utilizando o e-mail em vez do username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # Permitir autenticação com email ou username
        try:
            user = User.objects.get(Q(username=username) | Q(email=username))
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Em caso de email duplicado (não deveria acontecer se username for único, mas email pode não ser)
            user = User.objects.filter(email=username).order_by("id").first()

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
