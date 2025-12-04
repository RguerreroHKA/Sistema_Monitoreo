from django.apps import AppConfig


class MonitoreoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoreo'

    def ready(self):
        """
        Inicializar signals cuando la app está lista
        
        Importante: Sin esto, los signals NO se activan
        """
        import monitoreo.signals  # Importar signals para registrarlos