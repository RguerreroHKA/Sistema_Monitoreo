from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from .models import EventoDeAcceso

def calcular_severidad(anomaly_score):
    """
        Convierte score de anomalia a severidad

        anomaly_score: float (-inf a 1.0)
        - Valores < -0.7 = Muy anomalo
        - Valores -0.7 a -0.3 = Anomalo
        - Valores > -0.3 = Poco anomalo
    """

    if anomaly_score is None:
        return 'BAJA'
    
    if anomaly_score < -0.7:
        return 'CRITICA'
    elif anomaly_score < -0.3:
        return 'ALTA'
    elif anomaly_score < 0:
        return 'MEDIA'
    else:
        return 'BAJA'
    
def puede_enviar_alerta(evento_id, ventana_minutos=5):
    """
        Verifica si ya enviamos alerta para este evento
        Usa cache para evitar spam
        
        ventana_minutos: cuantos minutos esperar antes de enviar otra alerta
    """
    cache_key = f'alerta_enviada_{evento_id}'

    if cache.get(cache_key):
        return False # Se envio recientemente
    
    #Marca como enviado por N minutos
    cache.set(cache_key, True, ventana_minutos * 60)
    return True

def enviar_alerta_anomalia(evento):
    """
        Envia email cuando detecta anomalia
    """

    # 1. Calcular severidad
    severidad = calcular_severidad(evento.anomaly_score)
    evento.severidad = severidad
    evento.fecha_alerta = timezone.now()
    evento.save()

    # 2. Determinar destinatarios segun severidad
    if severidad == 'CRITICA':
        # Enviar a admin + security officer
        destinatarios = list(
            dict.fromkeys(
                [admin[1] for admin in settings.ADMINS] +
                [getattr(settings, 'SECURITY_OFFICER_EMAIL', None)]
            )
        )
    elif severidad == 'ALTA':
        #Enviar a admin
        destinatarios = [admin[1] for admin in settings.ADMINS]
    else:
        #Enviar solo a Monitor
        destinatarios = [getattr(settings, 'MONITOR_EMAIL', settings.DEFAULT_FROM_EMAIL)]

    # Filtrar Nones
    destinatarios = [e for e in destinatarios if e]

    if not destinatarios:
        print(f"No hay destinatarios configurados para severidad {severidad}")
        return False
    
    # 3. Construir email
    asunto = f'🚨 ANOMALÍA {severidad}: {evento.nombre_archivo}'

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
        5. Notificar al Oficial de Seguridad
        """
    elif severidad == 'ALTA':
        body += """
        🟠 REVISAR HOY:
        1. Verificar patrones de acceso
        2. Confirmar que el usuario es legítimo
        3. Considerar generar ticket en GLPI
        """
    else:
        body += """
        🟡 MONITOREO:
        1. Observar patrones similares
        2. Revisar si es patrón normal del usuario
        """

    body += f"""

    ════════════════════════════════════════
    DETALLES TÉCNICOS
    ════════════════════════════════════════
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
            recipient_list=destinatarios,
            fail_silently=False,
        )
        print(f'Email enviado a {destinatarios}')
        return True
    except Exception as e:
        print(f' Error enviando email: {e}')
        return False

def debe_enviar_alerta(evento):
    """
        Logica centralizada: ¿Enviamos alerta?
    """
        
    # No enviar si ya reportamos
    if evento.fecha_alerta is not None:
        return False
    
    # Evitar spam (maximo 1 alerta cada 5 minutos por evento)
    if not puede_enviar_alerta(evento.id, ventana_minutos=5):
        return False
    
    return True