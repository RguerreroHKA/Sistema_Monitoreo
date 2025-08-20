from django.urls import path
from . import views

urlpatterns = [
   path('registro/', views.registro_view, name = 'registro'),
   path('login/', views.login_view, name = 'login'),
   path('home/', views.home_view, name = 'home'),
   path('logout/', views.logout_view, name= 'logout'),
   path('admin-only/', views.vista_admin_only, name='admin_only'),
]