import logging
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from .models import GLPITicket

logger = logging.getLogger(__name__)
    
def puede_enviar_alerta(evento_id, ventana_minutos=5): # Subí la ventana a 60 min para evitar spam
    """
    Verifica si ya enviamos alerta para este evento recientemente.
    Usa cache para evitar spam si el script corre varias veces.
    """
    cache_key = f'alerta_email_enviada_{evento_id}'

    if cache.get(cache_key):
        return False # Se envio recientemente
    
    # Marca como enviado por N minutos
    cache.set(cache_key, True, ventana_minutos * 60)
    return True


def debe_enviar_alerta(evento):
    """
    Logica centralizada: ¿Enviamos alerta?
    """
        
    # 1. Filtro de Severidad: Solo alertar lo importante
    if evento.severidad not in ['ALTA', 'CRITICA']:
        return False
    
    # 2. Filtro de Base de Datos: Si ya tiene ticket, ya se atendió
    if hasattr(evento, 'ticket_glpi'):
        return False

    # 3. Filtro de Cache: Evitar correos repetidos en corto tiempo
    if not puede_enviar_alerta(evento.id):
        return False
    
    return True


def enviar_alerta_anomalia(evento):
    """
    Envia email cuando detecta anomalia
    """

    # Usamos la severidad que YA calculó la IA en analisis.py
    severidad = evento.severidad

    # Destinatario: Usamos el email configurado en settings
    destinatario = getattr(settings, 'GOOGLE_ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)

    if not destinatario:
        print(f"⚠️ No hay destinatario configurado para alertas.")
        return False
    
    # Construir email
    asunto = f'🚨 ANOMALÍA {severidad}: {evento.nombre_archivo}'

    motivo_texto = evento.motivo_anomalia if evento.motivo_anomalia else "Patrón atípico detectado"

    body = f"""
    ⚠️ ALERTA DE ANOMALÍA DETECTADA EN SGSI
    
    ════════════════════════════════════════
    INFORMACIÓN DEL EVENTO
    ════════════════════════════════════════
    Usuario: {evento.email_usuario}
    Archivo: {evento.nombre_archivo}
    Dirección IP: {evento.direccion_ip}
    Tipo de Evento: {evento.tipo_evento}
    Fecha/Hora: {evento.timestamp}
    Score de Anomalía: {evento.anomaly_score:.4f}
    Severidad: {severidad}

    🔍 MOTIVO DETECTADO:
    {motivo_texto}
    
    ════════════════════════════════════════
    RECOMENDACIONES
    ════════════════════════════════════════    
    """

    if severidad == 'CRITICA':
        body += """
        🔴 ACCIÓN INMEDIATA REQUERIDA:
        1. Verificar identidad del usuario
        2. Revisar permisos de acceso
        3. Contactar al usuario si es sospechoso
        4. Generar ticket en GLPI
        """
    elif severidad == 'ALTA':
        body += """
        🟠 REVISAR HOY:
        1. Verificar patrones de acceso
        2. Confirmar que el usuario es legítimo
        """
    else:
        body += """
        🟡 MONITOREO:
        1. Observar patrones similares
        """

    body += f"""
    ════════════════════════════════════════
    DETALLES TÉCNICOS
    ════════════════════════════════════════
    ID Evento Google: {evento.id_evento_google}
    Archivo ID: {evento.archivo_id}
    
    Acceder al dashboard: /monitoreo/dashboard/v2/
    
    ---
    Sistema Automático de Monitoreo SGSI
    The Factory HKA Venezuela
    """

    try:
        send_mail(
            subject=asunto,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinatario],
            fail_silently=False,
        )
        print(f"📧 Email de alerta enviado a {destinatario}")
        return True
    except Exception as e:
        print(f' Error enviando email: {e}')
        return False