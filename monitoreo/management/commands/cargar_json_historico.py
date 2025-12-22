import json
import pytz
import hashlib
from datetime import datetime
from django.core.management.base import BaseCommand
from monitoreo.models import EventoDeAcceso

class Command(BaseCommand):
    help = 'ETL Offline: Carga masiva de eventos históricos con filtrado y optimización por lotes.'

    def add_arguments(self, parser):
        parser.add_argument('ruta_json', type=str, help='Ruta al archivo JSON del reporte')

    def generar_id_unico(self, fecha_iso, email, archivo_id, accion):
        """
        Genera un ID único (Hash MD5) basado en el contenido del evento.
        Esto permite cargar múltiples JSONs sin duplicar eventos en la BD.
        """
        # Concatenamos los datos clave
        raw_string = f"{fecha_iso}_{email}_{archivo_id}_{accion}"
        # Retornamos el hash
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    def es_relevante(self, accion, archivo_titulo):
        """
        FILTRADO DE RUIDO (Requisito Sprint 4):
        Retorna True si el evento debe guardarse, False si es basura.
        """
        # 1. Ignorar archivos temporales de Office (empiezan con ~$)
        if archivo_titulo and archivo_titulo.startswith('~$'):
            return False
            
        # 2. (Opcional) Si quisieras ignorar sincronizaciones automáticas
        # if accion == 'sync_item_content': 
        #    return False
            
        return True

    def handle(self, *args, **options):
        ruta_archivo = options['ruta_json']
        self.stdout.write(self.style.WARNING(f"🚀 Iniciando ETL Offline desde: {ruta_archivo}"))

        local_tz = pytz.timezone("America/Caracas")
        lote_eventos = []
        TAMANO_LOTE = 2000  # La "carretilla" de 2000 eventos
        
        contadores = {'procesados': 0, 'guardados': 0, 'filtrados': 0, 'errores': 0}

        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                # Tu JSON tiene la lista en la clave 'eventos'
                lista_eventos = datos.get('eventos', [])

            self.stdout.write(f"📥 JSON cargado. Procesando {len(lista_eventos)} eventos...")

            for evento_dict in lista_eventos:
                contadores['procesados'] += 1
                
                try:
                    # --- TRANSFORMACIÓN (ETL) ---
                    
                    # 1. Parseo de Fecha
                    fecha_str = evento_dict.get('hora', '')
                    # Limpieza de typos comunes en fechas
                    fecha_str_limpia = fecha_str.replace("a.m..", "AM").replace("p.m..", "PM") \
                                                .replace("a.m.", "AM").replace("p.m.", "PM")
                    
                    try:
                        naive_timestamp = datetime.strptime(fecha_str_limpia, "%d/%m/%Y %I:%M %p")
                        aware_timestamp = local_tz.localize(naive_timestamp)
                    except ValueError:
                        contadores['errores'] += 1
                        continue

                    # 2. Parseo de Archivo (Tu formato es especial)
                    val_archivo = evento_dict.get('archivo', 'N/A')
                    archivo_id = 'unknown'
                    archivo_titulo = 'Sin Título'

                    # Caso A: "(ID_DEL_ARCHIVO)" -> Sin título, solo ID entre paréntesis
                    if val_archivo.startswith('(') and val_archivo.endswith(')'):
                        archivo_id = val_archivo[1:-1] # Quitar paréntesis
                        archivo_titulo = "Desconocido (Solo ID)"
                    
                    # Caso B: "Nombre del Archivo (ID_DEL_ARCHIVO)"
                    elif ' (' in val_archivo and val_archivo.endswith(')'):
                        partes = val_archivo.rsplit(' (', 1)
                        archivo_titulo = partes[0]
                        archivo_id = partes[1][:-1]
                    
                    # Caso C: Texto plano sin ID
                    else:
                        archivo_titulo = val_archivo

                    email = evento_dict.get('usuario', 'unknown')
                    accion = evento_dict.get('accion', 'unknown')
                    ip = evento_dict.get('ip', '0.0.0.0')

                    # --- FILTRADO (ETL) ---
                    if not self.es_relevante(accion, archivo_titulo):
                        contadores['filtrados'] += 1
                        continue

                    # --- CARGA (ETL) ---
                    
                    # Generamos el ID hash para evitar duplicados si cargamos varios JSON
                    id_google = self.generar_id_unico(aware_timestamp.isoformat(), email, archivo_id, accion)

                    nuevo_evento = EventoDeAcceso(
                        id_evento_google=id_google,
                        timestamp=aware_timestamp,
                        email_usuario=email,
                        archivo_id=archivo_id,
                        tipo_evento=accion,
                        nombre_archivo=archivo_titulo[:255], # Truncar por si acaso
                        direccion_ip=ip,
                        es_anomalia=False,
                        # Guardamos el JSON original en 'detalles' por si acaso
                        detalles=evento_dict 
                    )
                    
                    lote_eventos.append(nuevo_evento)

                    # Si la carretilla está llena, la mandamos a la BD
                    if len(lote_eventos) >= TAMANO_LOTE:
                        self._guardar_lote(lote_eventos)
                        contadores['guardados'] += len(lote_eventos)
                        lote_eventos = [] # Vaciar carretilla
                        self.stdout.write(f"   -> Progreso: {contadores['guardados']} guardados...", ending='\r')

                except Exception as e:
                    contadores['errores'] += 1

            # Guardar los últimos eventos que sobraron en la carretilla
            if lote_eventos:
                self._guardar_lote(lote_eventos)
                contadores['guardados'] += len(lote_eventos)

            self.stdout.write(self.style.SUCCESS("\n" + "="*40))
            self.stdout.write(self.style.SUCCESS(f"✅ ETL FINALIZADO"))
            self.stdout.write(f"   - Total Leídos: {contadores['procesados']}")
            self.stdout.write(f"   - Filtrados (Ruido): {contadores['filtrados']}")
            self.stdout.write(f"   - Errores Formato: {contadores['errores']}")
            self.stdout.write(self.style.SUCCESS(f"   - INSERTADOS EN BD: {contadores['guardados']}"))
            self.stdout.write(self.style.SUCCESS("="*40))

        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"Archivo no encontrado: {ruta_archivo}"))

    def _guardar_lote(self, lista_objetos):
        """
        Usa bulk_create con ignore_conflicts=True (SQLite)
        Esto es lo que permite cargar varios JSONs sin que explote por duplicados.
        """
        try:
            EventoDeAcceso.objects.bulk_create(lista_objetos, ignore_conflicts=True)
        except Exception as e:
            self.stderr.write(f"Error en lote: {e}")