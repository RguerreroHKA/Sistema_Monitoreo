from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import EventoDeAcceso

@receiver(post_save, sender=EventoDeAcceso)
def notificar_anomalia_detectada(sender, instance, created, **kwargs):
    """
    Señal que se dispara cuando se guarda un EventoDeAcceso
    
    Si es_anomalia=True, envía un email de notificación
    
    Conectado a: post_save de EventoDeAcceso
    Trigger: Cuando un evento se marca como anomalía
    
    Emails enviados a:
    - Administradores del sistema
    - Email configurado en settings.ANOMALIA_ALERT_EMAIL
    """

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1. SOLO ENVIAR SI ES ANOMALÍA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    if not instance.es_anomalia:
        return  # No es anomalía, no hacemos nada
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2. PREPARAR DESTINATARIOS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   
    destinatarios = []
    
    # Agregar emails de administradores
    for admin_email in [admin[1] for admin in settings.ADMINS]:
        destinatarios.append(admin_email)
    
    # Agregar email configurado en settings (si existe)
    if hasattr(settings, 'ANOMALIA_ALERT_EMAIL'):
        destinatarios.append(settings.ANOMALIA_ALERT_EMAIL)
    
    # Si no hay destinatarios, no enviar
    if not destinatarios:
        print("No hay destinatarios configurados para alertas de anomalía")
        return
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3. CONSTRUIR CONTENIDO DEL EMAIL
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    asunto = f"🚨 ALERTA: Anomalía Detectada en Sistema SGSI"
    
    mensaje_html = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; }}
                .header {{ background-color: #f44336; color: white; padding: 15px; border-radius: 4px; margin-bottom: 20px; text-align: center; }}
                .content {{ margin-bottom: 20px; }}
                .field {{ margin-bottom: 15px; }}
                .label {{ font-weight: bold; color: #333; }}
                .value {{ color: #666; word-break: break-word; }}
                .timestamp {{ color: #f44336; font-weight: bold; }}
                .footer {{ background-color: #f5f5f5; padding: 10px; border-top: 1px solid #ddd; text-align: center; font-size: 12px; color: #999; }}
                .icon {{ font-size: 48px; text-align: center; margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="icon">🚨</div>
                    <h1 style="margin: 0; font-size: 24px;">ALERTA DE ANOMALÍA DETECTADA</h1>
                </div>
                
                <div class="content">
                    <p style="color: #d32f2f; font-size: 16px;">
                        Se ha detectado una anomalía en el sistema de monitoreo SGSI.
                    </p>
                    
                    <div class="field">
                        <div class="label">👤 Usuario:</div>
                        <div class="value">{instance.email_usuario}</div>
                    </div>
                    
                    <div class="field">
                        <div class="label">📂 Archivo Accedido:</div>
                        <div class="value">{instance.nombre_archivo}</div>
                    </div>
                    
                    <div class="field">
                        <div class="label">🔍 Tipo de Evento:</div>
                        <div class="value">{instance.tipo_evento.upper()}</div>
                    </div>
                    
                    <div class="field">
                        <div class="label">📍 Dirección IP:</div>
                        <div class="value">{instance.direccion_ip}</div>
                    </div>
                    
                    <div class="field">
                        <div class="label">⏱️ Fecha y Hora:</div>
                        <div class="timestamp">{instance.timestamp.strftime('%d/%m/%Y %H:%M:%S')}</div>
                    </div>
                    
                    <div class="field">
                        <div class="label">📄 ID de Archivo:</div>
                        <div class="value">{instance.archivo_id}</div>
                    </div>
                </div>
                
                <div style="background-color: #fff3e0; padding: 15px; border-left: 4px solid #ff9800; margin-bottom: 20px;">
                    <p style="margin: 0; color: #333;">
                        <strong>⚠️ ACCIÓN RECOMENDADA:</strong><br>
                        Revisar inmediatamente este evento en el dashboard de administración.
                    </p>
                </div>
                
                <div class="footer">
                    <p>Este es un email automático generado por el Sistema de Monitoreo SGSI.</p>
                    <p>No responda a este correo. Visite el dashboard para más información.</p>
                </div>
            </div>
        </body>
    </html>
    """
    
    mensaje_texto = f"""
    🚨 ALERTA: ANOMALÍA DETECTADA EN SISTEMA SGSI
    
    Usuario: {instance.email_usuario}
    Archivo: {instance.nombre_archivo}
    Tipo de Evento: {instance.tipo_evento}
    Dirección IP: {instance.direccion_ip}
    Fecha y Hora: {instance.timestamp.strftime('%d/%m/%Y %H:%M:%S')}
    ID de Archivo: {instance.archivo_id}
    
    ---
    Este es un email automático. No responda a este correo.
    """

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. ENVIAR EMAIL
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    try:
        send_mail(
            subject=asunto,
            message=mensaje_texto,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=destinatarios,
            html_message=mensaje_html,
            fail_silently=False,
        )
        print(f"✅ Email de anomalía enviado a {len(destinatarios)} destinatarios")
    
    except Exception as e:
        print(f"Error al enviar email de anomalía: {str(e)}")
        # No lanzar excepción aquí para no interrumpir el flujo de guardado

@receiver(post_save, sender=EventoDeAcceso)
def registrar_evento_en_log(sender, instance, created, **kwargs):
    """
    Señal auxiliar para logging de eventos
    
    Registra cuando:
    - Se crea un nuevo evento
    - Un evento se marca como anomalía
    
    Útil para debugging y auditoría
    """
    
    if created:
        print(f"📌 Nuevo evento creado: {instance.email_usuario} accedió a {instance.nombre_archivo}")
    
    if instance.es_anomalia and created:
        print(f"🚨 ANOMALÍA NUEVA: {instance.email_usuario} desde {instance.direccion_ip}")