from django.urls import path
from . import views

app_name = "unidades"

urlpatterns = [
    path("", views.UnidadeListView.as_view(), name="list"),
    path("nova/", views.UnidadeCreateView.as_view(), name="create"),
    path("<int:pk>/", views.UnidadeDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.UnidadeUpdateView.as_view(), name="update"),
    path(
        "<int:pk>/usuarios/adicionar/",
        views.AddUserToUnidadeView.as_view(),
        name="add_user",
    ),
    path(
        "usuarios/<int:pk>/remover/",
        views.RemoveUserFromUnidadeView.as_view(),
        name="remove_user",
    ),
    path(
        "usuarios/<int:pk>/editar/",
        views.UserUpdateView.as_view(),
        name="update_user",
    ),
    path("perfil/", views.UserProfileView.as_view(), name="profile"),
    path(
        "perfil/senha/", views.UserPasswordChangeView.as_view(), name="password_change"
    ),
]
