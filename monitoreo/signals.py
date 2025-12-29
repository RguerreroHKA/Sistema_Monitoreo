from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import EventoDeAcceso
# Importamos EXACTAMENTE los nombres que definiste en utils_alertas
from .utils_alertas import debe_enviar_alerta, enviar_alerta_anomalia

@receiver(post_save, sender=EventoDeAcceso)
def notificar_anomalia_detectada(sender, instance, created, **kwargs):
    """
    Signal: Cuando se marca un evento como anomalía, envía alerta.
    Se ejecuta automáticamente después de instance.save()
    """
    
    # 1. Solo procesar si es una anomalía marcada
    if not instance.es_anomalia:
        return
    
    # 2. Verificar reglas de negocio (Severidad, Ticket existente, Spam)
    if not debe_enviar_alerta(instance):
        return
    
    # 3. Enviar alerta
    print(f"🚀 Signal activada: Enviando alerta para evento {instance.id}")
    enviar_alerta_anomalia(instance)