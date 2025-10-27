from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
   path('registro/', views.registro_view, name = 'registro'),
   path('login/', views.login_view, name = 'login'),
   path('home/', views.home_view, name = 'home'),
   path('logout/', views.logout_view, name= 'logout'),
   path('admin-only/', views.vista_admin_only, name='admin_only'),

   # Lista de usuarios (Solo admins)
   path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
   # Crear usuario (Solo admins)
   path('usuarios/crear_usuario/', views.crear_usuario, name='crear_usuario'),
   # Editar usuario (Solo admins)
   path('usuarios/editar_usuario/<int:usuario_id>/', views.editar_usuario, name='editar_usuario'),
   # Eliminar usuario (Solo admins)
   path('usuarios/accion_usuario/<int:usuario_id>/', views.accion_usuario, name='accion_usuario'),
]