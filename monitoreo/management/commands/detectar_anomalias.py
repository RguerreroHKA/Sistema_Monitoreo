from django.core.management.base import BaseCommand
from monitoreo.analisis import ejecutar_deteccion_anomalias

class Command(BaseCommand):
    help = 'Ejecuta la deteccion de anomalias con Isolation Forest sobre los eventos de acceso.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando deteccion de anomalias...")
        contador = ejecutar_deteccion_anomalias()
        self.stdout.write(self.style.SUCCESS(f"Finalizado. Se detectaron y marcaron {contador} eventos como anomalias."))