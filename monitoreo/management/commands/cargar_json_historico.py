import json
import pytz
from django.core.management.base import BaseCommand
from monitoreo.models import EventoDeAcceso
from datetime import datetime

# IMPORTANTE: Copiamos la función de guardado que ya teníamos
def guardar_eventos_en_db(eventos_relevantes):
    """
    Toma la lista de eventos relevantes y los carga en el modelo EventoDeAcceso.
    Usa update_or_create para evitar duplicados.
    """
    print(f"\n--- Cargando {len(eventos_relevantes)} eventos en la Base de Datos Django ---")
    
    eventos_creados = 0
    eventos_actualizados = 0
    
    # Define la zona horaria de tus datos. Asumimos Caracas (VET).
    local_tz = pytz.timezone("America/Caracas")

    for evento_dict in eventos_relevantes:
        try:
            # 1. Limpiamos el string de fecha
            fecha_str = evento_dict['hora']
            fecha_str_limpia = fecha_str.replace("a.m..", "AM").replace("p.m..", "PM")
            fecha_str_limpia = fecha_str_limpia.replace("a.m.", "AM").replace("p.m.", "PM")
            
            # 2. Parseamos el string a un datetime NAIVE
            try:
                naive_timestamp = datetime.strptime(fecha_str_limpia, "%d/%m/%Y %I:%M %p")
            except ValueError:
                print(f"Error parseando fecha: {fecha_str}. Saltando evento.")
                continue

            # 3. Hacemos que el datetime Naive sea AWARE, diciéndole su zona horaria real
            aware_timestamp = local_tz.localize(naive_timestamp)
            
            # Django ahora recibirá una fecha "aware" y la convertirá
            # automáticamente a UTC para guardarla en la BD. ¡Perfecto!

            # Extraer el ID del archivo
            archivo_completo = evento_dict.get('archivo', 'No disponible (N/A)')
            archivo_id = archivo_completo.split('(')[-1].replace(')', '')
            archivo_titulo = archivo_completo.split(' (')[0]

            obj, created = EventoDeAcceso.objects.update_or_create(
                timestamp=aware_timestamp, # <-- Usamos la fecha AWARE
                email_usuario=evento_dict.get('usuario', 'N/A'),
                archivo_id=archivo_id,
                tipo_evento=evento_dict.get('accion', 'N/A'),
                defaults={
                    'direccion_ip': evento_dict.get('ip', 'N/A'),
                    'nombre_archivo': archivo_titulo,
                    'es_anomalia': False
                }
            )
            
            if created:
                eventos_creados += 1
            else:
                eventos_actualizados += 1
        
        except Exception as e:
            print(f"Error al guardar evento: {e}")
            print(f"Datos del evento: {evento_dict}")

    print(f"✓ Carga a BD completada.")
    print(f"  -> Eventos nuevos creados: {eventos_creados}")
    print(f"  -> Eventos existentes actualizados: {eventos_actualizados}")


class Command(BaseCommand):
    help = 'Carga un archivo JSON de reporte histórico en la base de datos.'

    def add_arguments(self, parser):
        parser.add_argument('ruta_json', type=str, help='La ruta al archivo JSON del reporte.')

    def handle(self, *args, **options):
        ruta_archivo = options['ruta_json']
        self.stdout.write(self.style.WARNING(f"Cargando datos desde: {ruta_archivo}"))

        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            
            eventos = datos.get('eventos')
            if eventos is None:
                self.stderr.write(self.style.ERROR("El archivo JSON no tiene la clave 'eventos'."))
                return

            self.stdout.write(self.style.SUCCESS(f"Se encontraron {len(eventos)} eventos en el JSON."))
            
            guardar_eventos_en_db(eventos)
            
            self.stdout.write(self.style.SUCCESS("¡Carga histórica completada!"))

        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"No se encontró el archivo en: {ruta_archivo}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Ocurrió un error: {e}"))