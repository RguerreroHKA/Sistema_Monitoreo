import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from monitoreo.models import EventoDeAcceso

class Command(BaseCommand):
    help = 'Genera datos de eventos de acceso simulados para probar el modelo Isolation Forest'

    def handle(self, *args, **kwargs):
        self.stdout.write("Eliminando datos antiguos...")
        EventoDeAcceso.objects.all().delete()

        self.stdout.write("Generando datos simulados...")
        emails_usuarios = [f"usuario{i}@thefactoryhka.com" for i in range(10)]
        ips_normales = [f"192.168.1.{random.randint(10,50)}" for _ in range(5)]
        archivos = [(f"file_id_{i}", f"diseno_{i}.svg") for i in range(20)]

        # --- Generar Datos Normales (800 eventos) ---
        for _ in range(800):
            hora_evento = datetime.now() - timedelta(days=random.randint(0,6), hours=random.randint(8, 17))
            EventoDeAcceso.objects.create(
                email_usuario=random.choice(emails_usuarios),
                direccion_ip=random.choice(ips_normales),
                timestamp=hora_evento,
                archivo_id=random.choice(archivos)[0],
                nombre_archivo=random.choice(archivos)[1],
                tipo_evento=random.choice(['view', 'edit']),
            )
        
        # --- Generar Datos Anómalos (40 eventos) ---
        for _ in range(40):
            hora_evento = datetime.now() - timedelta(minutes=random.randint(1, 500), hours=random.choice([1, 2, 22, 23]))
            EventoDeAcceso.objects.create(
                email_usuario=random.choice(emails_usuarios),
                direccion_ip = f"118.99.8.{random.randint(1,254)}", #Rango  de IP inusual
                timestamp=hora_evento, #Horas inusuales
                archivo_id="id_confidencial_123", #Archivo Sensible
                nombre_archivo="financieros_2025.xlsx", 
                tipo_evento='download', # Tipo de evento de alto riesgo
            )
        
        self.stdout.write(self.style.SUCCESS("¡Se han generado los datos simulados exitosamente!"))
