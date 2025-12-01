from django.urls import path
from . import views

app_name = 'monitoreo'

urlpatterns = [
    # Vista Original solo mostraba anomalias (mantener para backward compatibility)
    path('dashboard/', views.dashboard_anomalias, name='dashboard'),

    # Rutas Nuevas
    # Dashboard completo
    path('dashboard/v2/', views.dashboard_monitoreo, name='dashboard-v2'),

    #APIs para sincronizacion y deteccion
    path('api/sincronizar/', views.api_sincronizar_eventos, name='api_sincronizar'),
    path('api/detectar/', views.api_ejecutar_deteccion, name='api_detectar'),
]