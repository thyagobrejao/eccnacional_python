import secrets
import string
from django.views.generic import ListView, CreateView, DetailView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.db.models import Q
from .models import Unidade, UserUnidade
from .forms import UnidadeForm, AddUserByEmailForm
from eccnacional.emailing import send_welcome_email

User = get_user_model()


def generate_random_password(length=12):
    """Gera uma senha aleatória segura."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get_all_descendant_ids(root_ids):
    """
    Retorna todos os IDs descendentes (recursivo) a partir de uma lista de IDs raiz.
    Usa uma única query para carregar todas as unidades e percorre em memória.
    """
    all_units = Unidade.objects.values("id", "parent_id")
    children_map = {}
    for u in all_units:
        if u["parent_id"]:
            children_map.setdefault(u["parent_id"], []).append(u["id"])

    all_ids = set(root_ids)
    queue = list(root_ids)
    while queue:
        uid = queue.pop()
        for child_id in children_map.get(uid, []):
            if child_id not in all_ids:
                all_ids.add(child_id)
                queue.append(child_id)
    return all_ids


class UnidadeListView(LoginRequiredMixin, ListView):
    """Lista unidades baseado nas permissões do usuário, com hierarquia recursiva."""

    model = Unidade
    template_name = "unidades/unidade_list.html"
    context_object_name = "unidades"
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser:
            queryset = Unidade.objects.all().select_related("parent")
        else:
            user_unidade_ids = list(
                UserUnidade.objects.filter(user=user, status=True).values_list(
                    "unidade_id", flat=True
                )
            )
            all_ids = get_all_descendant_ids(user_unidade_ids)
            queryset = Unidade.objects.filter(id__in=all_ids).select_related("parent")

        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(nome__icontains=search)

        return queryset.order_by("tipo", "nome")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Unidades"
        context["search_query"] = self.request.GET.get("q", "")

        user = self.request.user
        context["can_create"] = False

        if user.is_superuser:
            context["can_create"] = True
        else:
            user_unidades = UserUnidade.objects.filter(
                user=user, status=True
            ).select_related("unidade")
            if user_unidades.exists():
                min_tipo = min(uu.unidade.tipo for uu in user_unidades)
                context["can_create"] = min_tipo < Unidade.Tipo.PAROQUIA

        return context


class UnidadeCreateView(LoginRequiredMixin, CreateView):
    """Criar nova unidade."""

    model = Unidade
    form_class = UnidadeForm
    template_name = "unidades/unidade_form.html"
    success_url = reverse_lazy("unidades:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nova Unidade"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Unidade criada com sucesso!")
        return super().form_valid(form)


class UnidadeUpdateView(LoginRequiredMixin, UpdateView):
    """Editar unidade existente."""

    model = Unidade
    form_class = UnidadeForm
    template_name = "unidades/unidade_form.html"
    success_url = reverse_lazy("unidades:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Editar: {self.object.nome}"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Unidade atualizada com sucesso!")
        return super().form_valid(form)


class UnidadeDetailView(LoginRequiredMixin, DetailView):
    """Detalhes da unidade com lista de usuários."""

    model = Unidade
    template_name = "unidades/unidade_detail.html"
    context_object_name = "unidade"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.object.nome
        context["user_unidades"] = (
            UserUnidade.objects.filter(unidade=self.object)
            .select_related("user")
            .order_by("-status", "user__first_name")
        )
        context["add_user_form"] = AddUserByEmailForm()
        return context


class AddUserToUnidadeView(LoginRequiredMixin, View):
    """Adicionar usuário à unidade por email."""

    def post(self, request, pk):
        unidade = get_object_or_404(Unidade, pk=pk)
        form = AddUserByEmailForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]
            first_name = form.cleaned_data.get("first_name", "")
            last_name = form.cleaned_data.get("last_name", "")

            # Verificar se usuário já existe
            user = User.objects.filter(email=email).first()

            if user:
                # Usuário existe, verificar se já está vinculado
                existing_link = UserUnidade.objects.filter(
                    user=user, unidade=unidade
                ).first()
                if existing_link:
                    if existing_link.status:
                        messages.warning(
                            request,
                            f"O usuário {email} já está vinculado a esta unidade.",
                        )
                    else:
                        existing_link.status = True
                        existing_link.save()
                        messages.success(
                            request, f"Usuário {email} reativado na unidade!"
                        )
                else:
                    UserUnidade.objects.create(user=user, unidade=unidade, status=True)
                    messages.success(request, f"Usuário {email} adicionado à unidade!")
            else:
                # Criar novo usuário
                password = generate_random_password()
                username = email.split("@")[0]

                # Garantir username único
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )

                # Criar vínculo com unidade
                UserUnidade.objects.create(user=user, unidade=unidade, status=True)

                # Enviar email com credenciais
                self._send_welcome_email(user, password, unidade)

                messages.success(
                    request,
                    f"Novo usuário criado e adicionado! Um email foi enviado para {email} com as instruções de acesso.",
                )

        return redirect("unidades:detail", pk=pk)

    def _send_welcome_email(self, user, password, unidade):
        """Envia email de boas-vindas com credenciais."""
        return send_welcome_email(user, password, unidade)


class RemoveUserFromUnidadeView(LoginRequiredMixin, View):
    """Remover (desativar) usuário da unidade."""

    def post(self, request, pk):
        user_unidade = get_object_or_404(UserUnidade, pk=pk)
        unidade_pk = user_unidade.unidade_id

        user_unidade.status = False
        user_unidade.save()

        messages.success(
            request, f"Usuário {user_unidade.user.email} removido da unidade."
        )
        return redirect("unidades:detail", pk=unidade_pk)


from django.contrib.auth.views import PasswordChangeView
from .forms import UserProfileForm


class UserProfileView(LoginRequiredMixin, UpdateView):
    """Editar perfil do usuário logado."""

    model = User
    form_class = UserProfileForm
    template_name = "unidades/user_profile.html"
    success_url = reverse_lazy("unidades:profile")

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Meus Dados"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Dados atualizados com sucesso!")
        return super().form_valid(form)


class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Alterar senha do usuário."""

    template_name = "unidades/user_password_change.html"
    success_url = reverse_lazy("unidades:profile")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Alterar Senha"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Senha alterada com sucesso!")
        return super().form_valid(form)


class UserUpdateView(LoginRequiredMixin, UpdateView):
    """Editar dados de um usuário específico vinculado a uma unidade."""

    model = User
    form_class = UserProfileForm
    template_name = "unidades/user_form.html"

    def dispatch(self, request, *args, **kwargs):
        # Verificar se o usuário logado tem permissão para editar este usuário
        # Regra: Precisa ser superuser ou estar vinculado à mesma unidade com privilégios adequados
        # Por simplificação, vamos verificar se o usuario logado tem acesso a unidade do usuario editado

        target_user = self.get_object()

        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        # Buscar unidades do alvo
        target_unidades = UserUnidade.objects.filter(
            user=target_user, status=True
        ).values_list("unidade_id", flat=True)

        # Buscar unidades do logado
        my_unidades = UserUnidade.objects.filter(
            user=request.user, status=True
        ).values_list("unidade_id", flat=True)

        # Se houver intersecção (estão na mesma unidade) ou hierarquia (não implementado full aqui, mas básico)
        # Vamos assumir: Se eu posso VER a unidade (detail), posso editar os usuários dela, se eu tiver permissão de escrita.
        # A view DetailView já protege visualização.
        # Vamos permitir se compartilham unidade.
        if set(target_unidades).intersection(set(my_unidades)):
            return super().dispatch(request, *args, **kwargs)

        # TODO: Melhorar permissões. Por enquanto restrito a quem compartilha unidade ou superuser.
        messages.error(request, "Você não tem permissão para editar este usuário.")
        return redirect("home:index")  # Ou referer

    def get_success_url(self):
        # Redirecionar para a unidade de onde veio, se possivel.
        # Como um usuario pode ter varias unidades, vamos tentar pegar a unidade comum ou a referer.
        # Simplificação: Voltar para lista de unidades ou detail da primeira unidade em comum.

        target_user = self.object
        # Tenta achar a unidade contexto (se passada na URL seria melhor, mas aqui é só user ID)
        # Vamos usar um parametro GET 'unidade_id' se disponivel, ou descobrir.
        unidade_id = self.request.GET.get("unidade_id")
        if unidade_id:
            return reverse("unidades:detail", kwargs={"pk": unidade_id})

        # Fallback
        return reverse("unidades:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = (
            f"Editar Usuário: {self.object.get_full_name() or self.object.username}"
        )
        if self.request.GET.get("unidade_id"):
            context["unidade_id"] = self.request.GET.get("unidade_id")
        return context

    def form_valid(self, form):
        messages.success(
            self.request, f"Usuário {self.object.email} atualizado com sucesso!"
        )
        return super().form_valid(form)
