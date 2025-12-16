from django.db import models

# Create your models here.
class EventoDeAcceso(models.Model):
    """
        Modelo para registrar eventos de acceso de usuarios (Drive Activity API).
    """
    # Identificador único del evento provisto por Google (Vital para evitar duplicados al sincronizar)
    id_evento_google = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        help_text="ID unico del evento en Google Drive Activity API"
    )

    email_usuario = models.EmailField(help_text="Email del usuario que realizo la accion")
    direccion_ip = models.GenericIPAddressField(
        null=True, blank=True,
        help_text="Direccion IP desde dinde se realizo la accion"
    )
    timestamp = models.DateTimeField(help_text="Fecha y hora exacta del evento (UTC)")

    archivo_id = models.CharField(max_length=255, help_text="ID del archivo en Google Drive")
    nombre_archivo = models.CharField(max_length=255, null=True, blank=True)

    tipo_evento = models.CharField(max_length=50, help_text="Ej: 'view', 'download', 'edit', move")

    # Campos para IA y Auditoria
    es_anomalia = models.BooleanField(default=False, help_text="Marcado por el modelo de IA como una anomalía.")
    detalles = models.JSONField(null=True, blank=True, help_text="Datos originales en crudo de la API.")

    # Campos para Alertas
    anomaly_score = models.FloatField(
        null=True,
        blank=True,
        help_text='Score de Anomalia: 0.0 (Normal) a 1.0 (Anomalo)'
    )

    severidad = models.CharField(
        max_length=20,
        choices=[
            ('BAJA', 'Baja - Monitoreo'),
            ('MEDIA', 'Media - Revisar Pronto'),
            ('ALTA', 'Alta - Revisar Hoy'),
            ('CRITICA', 'Critica - Accion Inmediata'),
        ],
        null=True,
        blank=True,
        default=None,
        help_text='Nivel de criticidad de la anomalia'
    )

    fecha_alerta = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Cuando se envio la alerta'
    )

    def __str__(self):
        # Esto ayuda a que los registros se vean bien en el panel de admin
        fecha = self.timestamp.strftime('%Y-%m-%d %H:%M')
        return f"{fecha} - {self.email_usuario} -> {self.tipo_evento} en {self.nombre_archivo}"
    
    class Meta:
        # Ordena los eventos del mas reciente al mas antiguo
        ordering = ["-timestamp"]
        verbose_name = "Evento de Acceso"
        verbose_name_plural = "Eventos de Acceso"
        indexes = [
            models.Index(fields=['email_usuario', '-timestamp'], name='idx_email_timestamp'),
            models.Index(fields=['es_anomalia', '-timestamp'], name='idx_anomalia_timestamp'),
            models.Index(fields=['tipo_evento'], name='idx_tipo_evento'), # Simplificado
            models.Index(fields=['id_evento_google'], name='idx_id_google'), # Índice para búsquedas rápidas al sincronizar
            models.Index(fields=['timestamp'], name='idx_timestamp'),
        ]
