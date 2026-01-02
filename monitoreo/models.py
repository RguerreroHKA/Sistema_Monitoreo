from django.db import models
from django.utils import timezone

# Create your models here.
class EventoDeAcceso(models.Model):
    """
        Tabla principal de eventos (Logs de Auditoría).
        Corresponde a la entidad 'Event' de la propuesta.
        Incluye datos de 'Anomaly' desnormalizados para optimización de consultas.
    """
    # Identificador único del evento provisto por Google (Vital para evitar duplicados al sincronizar)
    id_evento_google = models.CharField(
        max_length=255,
        unique=True,
        help_text="ID unico del evento en Google Drive Activity API"
    )

    # Datos del Evento
    email_usuario = models.EmailField(
        help_text="Email del usuario que realizo la accion",
        verbose_name="Usuario Actor",
        db_index=True
    )
    tipo_evento = models.CharField(
        max_length=50, 
        db_index=True,
        help_text="Ej: 'view', 'download', 'edit', move"
    )
    archivo_id = models.CharField(
        max_length=255, 
        blank=True,
        null=True,
        db_index=True,
        help_text="ID del archivo en Google Drive",
    )

    nombre_archivo = models.CharField(max_length=255, null=True, blank=True)
    direccion_ip = models.GenericIPAddressField(
        null=True, blank=True,
        help_text="Direccion IP desde dinde se realizo la accion"
    )

    # Temporalidad
    timestamp = models.DateTimeField(
        verbose_name="Fecha y Hora",
        help_text="Fecha y hora exacta del evento (UTC)",
        db_index=True,
    )

    # Datos de Anomalia (Entidad Anomaly integrada)
    es_anomalia = models.BooleanField(
        default=False, 
        db_index=True,
        help_text="Marcado por el modelo de IA como una anomalía."
    )
    anomaly_score = models.FloatField(
        default=0.0,
        help_text='Score de Anomalia: 0.0 (Normal) a 1.0 (Anomalo)'
    )
    severidad = models.CharField(
        max_length=20, 
        default='BAJA',
        choices=[
            ('BAJA', 'Baja'),
            ('MEDIA', 'Media'),
            ('ALTA', 'Alta'),
            ('CRITICA', 'Crítica')
        ],
        db_index=True,
        help_text='Nivel de criticidad de la anomalia'
    )

    motivo_anomalia = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Explicación heurística de por qué se detectó como anomalía"
    )

    # Evidencia Forense
    detalles = models.JSONField(null=True, blank=True, help_text="Datos originales en crudo de la API.")

    class Meta:
        # Ordena los eventos del mas reciente al mas antiguo
        verbose_name = "Evento de Acceso"
        verbose_name_plural = "Eventos de Acceso"
        ordering = ["-timestamp"]
        
        # ÍNDICES COMPUESTOS (Requisito Sprint 3: queries comunes)
        indexes = [
            models.Index(fields=['email_usuario', 'timestamp'], name='idx_user_time'),
            models.Index(fields=['es_anomalia', 'severidad'], name='idx_anomaly_sev'),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.email_usuario} - {self.tipo_evento}"
    
class GLPITicket(models.Model):
    """
        Tabla para la integración con Mesa de Ayuda.
        Corresponde a la entidad "GLPITicket" de la propuesta.
    """
    ESTADOS_TICKET = [
        ('nuevo', 'Nuevo'),
        ('en_curso', 'En Curso'),
        ('resuelto', 'Resuelto'),
        ('cerrado', 'Cerrado'),
    ]

    # Relacion con la anomalía (Un evento puede generar un ticket)
    evento = models.OneToOneField(
        EventoDeAcceso, 
        on_delete=models.CASCADE,
        related_name='ticket_glpi',
        verbose_name="Evento Anómalo"
    )

    ticket_id = models.IntegerField(
        unique=True,
        help_text="ID del ticket en el sistema GLPI externo"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_TICKET,
        default='nuevo',
    )

    # Campos de Auditoria del Ticket
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    enlace_glpi = models.URLField(
        blank=True,
        null=True,
        help_text="Link directo al ticket en GLPI",
    )

    class Meta:
        verbose_name = "Ticket GLPI"
        verbose_name_plural = "Tickets GLPI"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Ticket GLPI #{self.ticket_id} - {self.estado}"
            
    
