### MODIFICACIÓN DJANGO: Imports necesarios para Django ###
import os
import time
import json
import pickle
from pathlib import Path
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand
from django.conf import settings
from monitoreo.models import EventoDeAcceso # <- Nuestro modelo de BD
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
# import re # No lo usaremos por ahora

# --- CONFIGURACIÓN CRÍTICA (Leída desde settings.py) ---
SERVICE_ACCOUNT_FILE = settings.GOOGLE_SERVICE_ACCOUNT_FILE
EMAIL_ADMIN = settings.GOOGLE_ADMIN_EMAIL
TARGET_FOLDER_ID = settings.GOOGLE_TARGET_FOLDER_ID

SCOPES = [
    'https://www.googleapis.com/auth/admin.reports.audit.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

# AJUSTA ESTOS VALORES según necesites
DIAS_A_CONSULTAR = 30  # Empecemos con 30 días para pruebas
UMBRAL_DIAS_TABLA = 30
MAX_WORKERS = 5
BATCH_SIZE = 1000
MAX_RETRIES = 3

CACHE_DIR = Path("cache_sgsi")
INVENTORY_CACHE_FILE = CACHE_DIR / "inventory_cache.pkl"
CACHE_EXPIRY_HOURS = 24

# --- INICIO DE TU SCRIPT ORIGINAL (adaptado a funciones) ---

def autenticar_cuenta_servicio():
    print("Autenticando con la cuenta de Servicio...")
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        delegated_creds = creds.with_subject(EMAIL_ADMIN)
        print("Autenticacion exitosa.")
        return delegated_creds
    except FileNotFoundError:
        print(f"ERROR: No se encontró el archivo de credenciales '{SERVICE_ACCOUNT_FILE}'.")
        print("Asegúrate de que esté en la raíz del proyecto y configurado en settings.py")
        return None
    except Exception as e:
        print(f"Error durante la autenticacion: {e}")
        return None

def cargar_inventario_cache():
    if not INVENTORY_CACHE_FILE.exists(): return None
    try:
        with open(INVENTORY_CACHE_FILE, 'rb') as f:
            cache_data = pickle.load(f)
        cache_time = cache_data.get('timestamp')
        if cache_time:
            age_hours = (datetime.now() - cache_time).total_seconds() / 3600
            if age_hours < CACHE_EXPIRY_HOURS:
                print(f"✓ Usando inventario en cache (creado hace {age_hours:.1f} horas)")
                return cache_data['file_ids'], cache_data['folder_count']
            else:
                print(f"⚠️  Cache expirado (edad: {age_hours:.1f} horas)")
        return None
    except Exception as e:
        print(f"Error leyendo cache: {e}")
        return None

def guardar_inventario_cache(file_ids, folder_count):
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        cache_data = {
            'timestamp': datetime.now(),
            'file_ids': file_ids,
            'folder_count': folder_count
        }
        with open(INVENTORY_CACHE_FILE, 'wb') as f:
            pickle.dump(cache_data, f)
        print("✓ Inventario guardado en cache")
    except Exception as e:
        print(f"⚠️  No se pudo guardar cache: {e}")

def lista_ids_archivos_optimizado(service, folder_id):
    print("Construyendo inventario optimizado...")
    all_folder_ids = {folder_id}
    folders_to_process = [folder_id]
    folder_count = 0
    
    while folders_to_process:
        current_folders = folders_to_process[:50]
        folders_to_process = folders_to_process[50:]
        
        for current_folder in current_folders:
            page_token = None
            while True:
                try:
                    response = service.files().list(
                        q=f"'{current_folder}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                        includeItemsFromAllDrives=True,
                        supportsAllDrives=True,
                        pageToken=page_token,
                        fields='nextPageToken, files(id)',
                        pageSize=1000
                    ).execute()
                    
                    for item in response.get("files", []):
                        folder_id_item = item.get('id')
                        if folder_id_item not in all_folder_ids:
                            all_folder_ids.add(folder_id_item)
                            folders_to_process.append(folder_id_item)
                            folder_count += 1
                    
                    page_token = response.get('nextPageToken')
                    if not page_token:
                        break
                except HttpError as error:
                    print(f'Error al listar carpetas: {error}')
                    break
    
    print(f"  -> Encontradas {folder_count} carpetas")
    
    file_ids = set()
    folder_list = list(all_folder_ids)
    
    for i in range(0, len(folder_list), 20):
        batch_folders = folder_list[i:i+20]
        folder_conditions = " or ".join([f"'{fid}' in parents" for fid in batch_folders])
        query = f"({folder_conditions}) and mimeType != 'application/vnd.google-apps.folder' and trashed=false"
        
        page_token = None
        while True:
            try:
                response = service.files().list(
                    q=query,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    pageToken=page_token,
                    fields='nextPageToken, files(id)',
                    pageSize=1000
                ).execute()
                
                for item in response.get("files", []):
                    file_ids.add(item.get('id'))
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            except HttpError as error:
                print(f'Error al listar archivos: {error}')
                break
            
        if (i + 20) % 100 == 0 and i > 0:
            print(f"  -> Procesadas {min(i + 20, len(folder_list))} de {len(folder_list)} carpetas...")
    
    return file_ids, folder_count

def obtener_pagina_auditoria(admin_service, start_time_iso, page_token=None):
    for intento in range(MAX_RETRIES):
        try:
            results = admin_service.activities().list(
                userKey='all',
                applicationName='drive',
                startTime=start_time_iso,
                maxResults=BATCH_SIZE,
                pageToken=page_token
            ).execute()
            return results.get('items', []), results.get('nextPageToken')
        except HttpError as error:
            if intento < MAX_RETRIES - 1:
                time.sleep(2 ** intento)
                continue
            return [], None
        except Exception as e:
            if intento < MAX_RETRIES - 1:
                time.sleep(2 ** intento)
                continue
            return [], None
    return [], None

def consultar_auditoria_optimizado(credentials, start_time_iso, target_file_ids):
    admin_service = build('admin', 'reports_v1', credentials=credentials)
    
    print("  Obteniendo primera página...")
    first_page, first_token = obtener_pagina_auditoria(admin_service, start_time_iso)
    
    eventos_relevantes = filtrar_pagina(first_page, target_file_ids)
    total_eventos = len(first_page)
    
    if not first_token:
        print(f"  ✓ Solo hay una página. Total: {total_eventos} eventos")
        return eventos_relevantes, total_eventos
    
    print(f"  Primera página: {len(first_page)} eventos, {len(eventos_relevantes)} relevantes")
    print("  Descargando páginas restantes (paralelismo conservador)...")
    
    target_ids_set = set(target_file_ids)
    pending_tokens = [first_token]
    processed_tokens = set()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        completed = 1
        
        while pending_tokens or futures:
            while pending_tokens and len(futures) < MAX_WORKERS:
                token = pending_tokens.pop(0)
                if token not in processed_tokens:
                    processed_tokens.add(token)
                    service = build('admin', 'reports_v1', credentials=credentials)
                    future = executor.submit(procesar_pagina_completa, service, start_time_iso, token, target_ids_set)
                    futures[future] = token
            
            if futures:
                try:
                    done_futures = []
                    for future in as_completed(futures.keys(), timeout=90):
                        done_futures.append(future)
                        break
                    
                    for future in done_futures:
                        try:
                            page_eventos, next_token, num_eventos = future.result(timeout=5)
                            
                            if page_eventos is not None:
                                eventos_relevantes.extend(page_eventos)
                                total_eventos += num_eventos
                                completed += 1
                                
                                if next_token and next_token not in processed_tokens:
                                    pending_tokens.append(next_token)
                                
                                if completed % 100 == 0:
                                    print(f"  -> Páginas: {completed} | Total eventos: {total_eventos:,} | Relevantes: {len(eventos_relevantes):,}")
                            
                            del futures[future]
                        except Exception as e:
                            print(f"  ⚠️  Error en página: {e}")
                            if future in futures:
                                token = futures[future]
                                if token not in pending_tokens:
                                    processed_tokens.discard(token)
                                    pending_tokens.append(token)
                                del futures[future]
                
                except Exception as e:
                    print(f"  ⚠️  Timeout en lote, continuando...")
                    time.sleep(1)
    
    print(f"  ✓ Descarga completada: {completed} páginas")
    return eventos_relevantes, total_eventos

def procesar_pagina_completa(admin_service, start_time_iso, page_token, target_ids_set):
    activities, next_token = obtener_pagina_auditoria(admin_service, start_time_iso, page_token)
    if not activities:
        return [], next_token, 0
    
    eventos = filtrar_pagina(activities, target_ids_set)
    return eventos, next_token, len(activities)

def filtrar_pagina(activities, target_ids_set):
    eventos_relevantes = []
    
    for activity in activities:
        actor_email = activity.get('actor', {}).get('email', 'Actor Desconocido')
        event_time_str = activity['id']['time']
        ip_address = activity.get('ipAddress', 'N/A')
        
        for event in activity['events']:
            event_name = event['name']
            doc_id = None
            doc_title = "No disponible"
            
            for p in event.get('parameters', []):
                if 'name' in p and 'value' in p:
                    if p['name'] == 'doc_id':
                        doc_id = p['value']
                    elif p['name'] == 'doc_title':
                        doc_title = p['value']
            
            if doc_id and doc_id in target_ids_set:
                try:
                    ### MODIFICACIÓN DJANGO: Necesitamos el objeto datetime, no el string formateado ###
                    utc_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
                    
                    eventos_relevantes.append({
                        "timestamp": utc_time, # <- ENVIAMOS EL OBJETO DATETIME
                        "usuario": actor_email,
                        "accion": event_name,
                        "archivo_id": doc_id,
                        "archivo_titulo": doc_title,
                        "ip": ip_address,
                        "detalles_json": activity # <- Guardamos el evento crudo
                    })
                except Exception as e:
                    print(f"Error parseando evento: {e}")
    
    return eventos_relevantes

# --- FIN DE TU SCRIPT ORIGINAL ---


### MODIFICACIÓN DJANGO: Nueva función para cargar datos en la BD ###
def guardar_eventos_en_db(eventos_relevantes):
    """
        Toma la lista de eventos relevantes y los carga en el modelo EventoDeAcceso.
        Usa el id_evento_google para evitar duplicados reales.
    """
    print(f"\n--- Paso 3: Cargando {len(eventos_relevantes)} eventos en la Base de Datos Django ---")
    
    eventos_creados = 0
    eventos_actualizados = 0
    
    for evento in eventos_relevantes:
        try:
            # Extraemos el ID único del evento de Google (está dentro de 'detalles_json')
            # La estructura usual es: id: { time: "...", uniqueQualifier: "..." }
            # Usaremos una combinación de time + uniqueQualifier como ID único
            detalles = evento.get('detalles_json', {})
            id_info = detalles.get('id', {})
            unique_qualifier = id_info.get('uniqueQualifier', 'no_qualifier')
            time_str = id_info.get('time', str(evento['timestamp']))

            # Generamos un ID robusto
            google_id = f"{time_str}_{unique_qualifier}"

            # Usuamos update_or_create basandonos en el ID DE GOOGLE
            obj, created = EventoDeAcceso.objects.update_or_create(
                id_evento_google = google_id, # Usamos el ID único
                defaults={
                    'timestamp': evento['timestamp'],
                    'email_usuario': evento['usuario'],
                    'archivo_id': evento['archivo_id'],
                    'nombre_archivo': evento['archivo_titulo'],
                    'tipo_evento': evento['accion'],
                    'direccion_ip': evento['ip'],
                    'detalles': detalles,
                    # 'es_anomalia' No se toca aqui, se deja como esté o False si es nuevo
                }
            )
            
            if created:
                eventos_creados += 1
            else:
                eventos_actualizados += 1
        
        except Exception as e:
            # --- MANEJO DE ERRORES ---
            # Si el error es específicamente por el campo de IP (ej: IPv6 malformada)
            if "direccion_ip" in str(e):
                 print(f"Error guardando IP: {evento['ip']}. Reintentando con IP genérica...")

                 # --- INTENTO 2: REINTENTO ---
                 try:
                    obj, created = EventoDeAcceso.objects.update_or_create(
                        id_evento_google=google_id,
                        defaults={
                            'timestamp': evento['timestamp'],
                            'email_usuario': evento['usuario'],
                            'archivo_id': evento['archivo_id'],
                            'nombre_archivo': evento['archivo_titulo'],
                            'tipo_evento': evento['accion'],
                            'direccion_ip': '0.0.0.0', # <--- Usamos IP neutra para salvar el evento
                            'detalles': detalles, # El JSON sí conserva la IP original para auditoría forense
                        }
                    )
                    if created: eventos_creados += 1
                    else: eventos_actualizados += 1
                    print("   -> ¡Evento salvado exitosamente!")

                 except Exception as e2:
                     print(f"Error fatal incluso al reintentar: {e2}")
            else:
                print(f"Error no recuperable al guardar evento {evento.get('accion')}: {e}")

    print(f"✓ Carga a BD completada.")
    print(f"  -> Eventos nuevos creados: {eventos_creados}")
    print(f"  -> Eventos existentes actualizados: {eventos_actualizados}")


# ============================================================================
# CLASE GoogleDriveCollector (NUEVA - para usar en views.py)
# ============================================================================

class GoogleDriveCollector:
    """
    Clase que encapsula toda la lógica de recolección de eventos de Google Drive.
    Usada por las vistas y APIs.
    """
    
    def __init__(self):
        self.credentials = None
        self.target_file_ids = None
        
    def obtener_eventos(self):
        """
        Obtiene eventos de Google Drive Activity API.
        
        Retorna lista de eventos crudos de la API.
        """
        # 1. Autenticar
        self.credentials = autenticar_cuenta_servicio()
        if not self.credentials:
            print("❌ Fallo en autenticación")
            return []
        
        # 2. Obtener inventario
        cached_inventory = cargar_inventario_cache()
        if cached_inventory:
            self.target_file_ids, _ = cached_inventory
        else:
            drive_service = build('drive', 'v3', credentials=self.credentials)
            self.target_file_ids, _ = lista_ids_archivos_optimizado(
                drive_service, 
                TARGET_FOLDER_ID
            )
            guardar_inventario_cache(self.target_file_ids, _)
        
        if not self.target_file_ids:
            print("❌ No hay archivos para monitorear")
            return []
        
        # 3. Consultar auditoría
        start_time_iso = (
            datetime.now(timezone.utc) - timedelta(days=DIAS_A_CONSULTAR)
        ).isoformat()
        
        eventos_relevantes, total_eventos = consultar_auditoria_optimizado(
            self.credentials,
            start_time_iso,
            self.target_file_ids
        )
        
        print(f"✅ Recolector obtuvo {len(eventos_relevantes)} eventos")
        return eventos_relevantes

# Modificacion para Backup automático y refresh de inventory_cache.pkl

# ============================================================================
# NUEVAS FUNCIONES: Backup automático y refresh de token (VERSIÓN CORRECTA)
# Rutas adaptadas para cache_sgsi/
# ============================================================================

def refrescar_token_google():
    """
    🔄 Elimina inventory_cache.pkl CADUCADO para forzar re-autenticación.
    
    Se ejecuta ANTES de obtener_eventos() si el token está viejo.
    
    Busca en:
    - cache_sgsi/inventory_cache.pkl
    - cache_sqls/token.pickle (compatibilidad)
    """
    try:
        base_dir = Path(settings.BASE_DIR)
        cache_file = base_dir / 'cache_sgsi' / 'inventory_cache.pkl'
        
        if not cache_file.exists():
            print("No hay token en cache. Se generará uno nuevo.")
            return True
        
        # 🔍 VERIFICAR SI ESTÁ CADUCADO
        try:
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            cache_time = cache_data.get('timestamp')
            if cache_time:
                age_hours = (datetime.now() - cache_time).total_seconds() / 3600
                
                if age_hours >= CACHE_EXPIRY_HOURS:  # 24 horas
                    # ✅ CADUCADO → Eliminar
                    cache_file.unlink()
                    print(f"Token caducado eliminado (edad: {age_hours:.1f} horas)")
                    return True
                else:
                    # ❌ AÚN VÁLIDO → No tocar
                    print(f"Token aún válido (edad: {age_hours:.1f} horas)")
                    return True
        except Exception as e:
            print(f"Error verificando token: {e}")
            return True
        
        return True
        
    except Exception as e:
        print(f"Error refrescando token: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def guardar_reporte_json_desde_bd():
    """
    🔄 Exporta TODOS los eventos desde BD a cache_sgsi/reporte_historico.json
    
    Esto permite que cargar_json_historico.py restaure la información si falta.
    
    Se guarda en:
    - cache_sgsi/reporte_historico.json ← Ubicación CORRECTA
    """
    import json
    
    try:
        base_dir = Path(settings.BASE_DIR)
        cache_dir = base_dir / 'cache_sgsi'
        report_path = cache_dir / 'reporte_historico.json'
        
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📁 Exportando eventos a JSON: {report_path}")
        
        # Obtener TODOS los eventos de la BD
        eventos_db = EventoDeAcceso.objects.all().order_by('-timestamp').values(
            'email_usuario',
            'direccion_ip',
            'timestamp',
            'archivo_id',
            'nombre_archivo',
            'tipo_evento',
            'es_anomalia',
            'detalles'
        )
        
        # Convertir a lista y formatear para JSON
        eventos_list = []
        for evento in eventos_db:
            evento_dict = dict(evento)
            timestamp = evento_dict['timestamp']
            
            # Convertir datetime a string ISO
            if timestamp:
                timestamp_str = timestamp.isoformat()
            else:
                timestamp_str = None
            
            # Formatear para el JSON original (con 'hora' formateada)
            from datetime import datetime
            if timestamp:
                hora_formateada = timestamp.strftime("%d/%m/%Y %I:%M %p")
            else:
                hora_formateada = "N/A"
            
            eventos_list.append({
                "hora": hora_formateada,
                "usuario": evento_dict['email_usuario'],
                "accion": evento_dict['tipo_evento'],
                "archivo": f"({evento_dict['archivo_id']})",  # Simplificado
                "ip": evento_dict['direccion_ip']
            })
        
        # Crear estructura del reporte (formato original)
        # Obtener lista de archivo_ids únicos
        archivo_ids_unicos = EventoDeAcceso.objects.values_list('archivo_id', flat=True).distinct()

        reporte = {
            'periodo_dias': DIAS_A_CONSULTAR,
            'fecha_consulta': datetime.now(timezone.utc).isoformat(),
            'total_eventos_procesados': len(eventos_list),
            'eventos_relevantes': len([e for e in eventos_list if e['usuario']]),
            'archivos_monitoreados': len(set(archivo_ids_unicos)),
            'eventos': eventos_list
        }
        
        # Guardar a JSON con encoding UTF-8
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        print(f"Reporte JSON actualizado: {len(eventos_list)} eventos guardados")
        print(f"   Ubicación: {report_path}")
        
        return True
        
    except Exception as e:
        print(f"Error guardando reporte JSON: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# Fin de Modificacion para Backup automático y refresh de inventory_cache.pkl

### MODIFICACIÓN DJANGO: Envoltura del comando ###
class Command(BaseCommand):
    help = 'Ejecuta el script real de recolección de eventos de Google Drive y los carga en la base de datos.'

    def handle(self, *args, **kwargs):
        """Función principal (reemplaza tu 'correr_monitoreo' y '__main__')"""
        
        self.stdout.write(self.style.SUCCESS("\n" + "="*80))
        self.stdout.write(self.style.SUCCESS("INICIANDO RECOLECCIÓN REAL DE EVENTOS DE GOOGLE DRIVE"))
        self.stdout.write(self.style.SUCCESS("="*80))
        
         # 🔄 NUEVA LÍNEA - Refrescar token ANTES de obtener eventos
        print("\n📌 Verificando token de autenticación...")
        refrescar_token_google()

        start_time_total = time.time()
        
        credentials = autenticar_cuenta_servicio()
        if not credentials:
            self.stderr.write(self.style.ERROR("Fallo en la autenticación. Abortando."))
            return

        # --- Paso 1: Inventario (con cache) ---
        self.stdout.write(self.style.WARNING('\n--- Paso 1: Inventario de Archivos (con cache) ---'))
        start_time_inventory = time.time()
        
        cached_inventory = cargar_inventario_cache()
        
        if cached_inventory:
            target_file_ids, total_folders = cached_inventory
            duration_inventory = time.time() - start_time_inventory
            print(f"✓ Inventario cargado desde cache en {duration_inventory:.2f} segundos")
        else:
            drive_service = build('drive', 'v3', credentials=credentials)
            target_file_ids, total_folders = lista_ids_archivos_optimizado(drive_service, TARGET_FOLDER_ID)
            guardar_inventario_cache(target_file_ids, total_folders)
            duration_inventory = time.time() - start_time_inventory
            print(f'✓ Inventario completado en {duration_inventory:.2f} segundos')
        
        if not target_file_ids:
            self.stderr.write(self.style.ERROR("No se encontraron archivos. Finalizando."))
            return
        
        print(f"  -> 📄 Archivos a monitorear: {len(target_file_ids):,}")
        print(f"  -> 📁 Carpetas encontradas: {total_folders:,}")
        
        # --- Paso 2: Auditoría optimizada ---
        self.stdout.write(self.style.WARNING(f'\n--- Paso 2: Consultando auditoría (últimos {DIAS_A_CONSULTAR} días) ---'))
        start_time_audit = time.time()
        start_time_iso = (datetime.now(timezone.utc) - timedelta(days=DIAS_A_CONSULTAR)).isoformat()
        
        try:
            eventos_relevantes, total_eventos = consultar_auditoria_optimizado(credentials, start_time_iso, target_file_ids)
            
            duration_audit = time.time() - start_time_audit
            print(f"✓ Consulta completada en {duration_audit:.2f} segundos ({duration_audit/60:.2f} minutos)")
            print(f"  -> Total de eventos procesados: {total_eventos:,}")
            print(f"  -> Eventos relevantes encontrados: {len(eventos_relevantes):,}")
            
            # --- Paso 3: Cargar en BD (Reemplaza la impresión y guardado JSON) ---
            if eventos_relevantes:
                guardar_eventos_en_db(eventos_relevantes)

            # 📁 NUEVA LÍNEA - Crear backup JSON automático
            print("\n📁 Creando backup en JSON...")
            guardar_reporte_json_desde_bd()

            if not eventos_relevantes:
                self.stdout.write(self.style.SUCCESS("\nNo se encontraron eventos nuevos para cargar en la BD."))
            
            duration_total = time.time() - start_time_total
            self.stdout.write(self.style.SUCCESS("\n" + "="*80))
            self.stdout.write(self.style.SUCCESS(f"✓ RECOLECCIÓN COMPLETADA en {duration_total:.2f} segundos ({duration_total/60:.2f} minutos)"))
            self.stdout.write(self.style.SUCCESS("="*80))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"\nERROR INESPERADO: {e}"))
            import traceback
            traceback.print_exc()