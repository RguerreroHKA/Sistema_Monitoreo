from django.db import models

# Create your models here.
class EventoDeAcceso(models.Model):
    """
        Modelo para registrar eventos de acceso de usuarios
    """
    email_usuario = models.EmailField(help_text="Email del usuario que realizo la accion")
    direccion_ip = models.GenericIPAddressField(help_text="Direccion IP desde dinde se realizo la acciob")
    timestamp = models.DateTimeField()
    archivo_id = models.CharField(max_length=255)
    nombre_archivo = models.CharField(max_length=255)
    tipo_evento = models.CharField(max_length=50, help_text="Ej: 'view', 'download', 'edit'")
    es_anomalia = models.BooleanField(default=False, help_text="Marcado por el modelo de IA como una anomalía.")
    detalles = models.JSONField(null=True, blank=True, help_text="Datos originales en crudo de la API.")

    def __str__(self):
        # Esto ayuda a que los registros se vean bien en el panel de admin
        return f"{self.timestamp.strftime("%Y-%m-%d %H:%M")} - {self.email_usuario} accedió a {self.nombre_archivo}"
    
    class Meta:
        # Ordena los eventos del mas reciente al mas antiguo
        ordering = ["-timestamp"]
