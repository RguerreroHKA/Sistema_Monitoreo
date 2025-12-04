from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import EventoDeAcceso
from .utils_alertas import debe_enviar_alerta, enviar_alerta_anomalia


@receiver(post_save, sender=EventoDeAcceso)
def notificar_anomalia_detectada(sender, instance, created, **kwargs):
    """
    Signal: Cuando se marca un evento como anomalía, envía alerta
    """
    
    # Solo procesar si es NUEVA anomalía
    if not instance.es_anomalia:
        return
    
    # Verificar si ya enviamos alerta
    if not debe_enviar_alerta(instance):
        return
    
    # Enviar alerta
    print(f"Enviando alerta para evento: {instance.id}")
    enviar_alerta_anomalia(instance)


# Registrar signals cuando se importa el módulo
default_app_config = 'monitoreo.apps.MonitoreoConfig'
