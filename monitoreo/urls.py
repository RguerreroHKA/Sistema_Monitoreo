from django.urls import path
from . import views

app_name = 'monitoreo'
urlpatterns = [
    path('dashboard/', views.dashboard_anomalias, name='dashboard')
]