### MODIFICACIÓN DJANGO: Imports necesarios para Django ###
import os
import time
import json
import pickle
import hashlib
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

# Parametros Sprint4
# AJUSTA ESTOS VALORES según necesites
DIAS_A_CONSULTAR = 30  # Empecemos con 30 días para pruebas
#UMBRAL_DIAS_TABLA = 30
MAX_WORKERS = 5
BATCH_SIZE = 1000
MAX_RETRIES = 3

CACHE_DIR = Path("cache_sgsi")
INVENTORY_CACHE_FILE = CACHE_DIR / "inventory_cache.pkl"
CACHE_EXPIRY_HOURS = 24

# --- FUNCIONES AUXILIARES ---

def generar_id_unico(fecha_iso, email, archivo_id, accion):
    """
        Generar un ID unico (Hash MD5) identico al del script de carga historica.
        Esto evita duplicados al mezclar datos offline y online.
    """
    # Si la fecha es un objeto datetime, convertir a ISO string
    if isinstance(fecha_iso, datetime):
        fecha_iso = fecha_iso.isoformat()

    raw_string = f"{fecha_iso}_{email}_{archivo_id}_{accion}"
    return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

def autenticar_cuenta_servicio():
    print("Autenticando con la cuenta de Servicio...")
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        delegated_creds = creds.with_subject(EMAIL_ADMIN)
        print("Autenticacion exitosa.")
        return delegated_creds
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
                except HttpError:
                    break
    
    print(f"  -> Encontradas {folder_count} carpetas")
    
    file_ids = set()
    folder_list = list(all_folder_ids)
    
    # Batch processing para archivos
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
            except HttpError:
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
                            if future in futures:
                                token = futures[future]
                                if token not in pending_tokens:
                                    processed_tokens.discard(token)
                                    pending_tokens.append(token)
                                del futures[future]
                
                except Exception:
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
                    utc_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
                    
                    eventos_relevantes.append({
                        "timestamp": utc_time,
                        "usuario": actor_email,
                        "accion": event_name,
                        "archivo_id": doc_id,
                        "archivo_titulo": doc_title,
                        "ip": ip_address,
                        "detalles_json": activity
                    })
                except Exception:
                    pass
    
    return eventos_relevantes

# --- GUARDADO EN BD ESTANDARIZADO (HASH MD5) ---

def guardar_eventos_en_db(eventos_relevantes):
    """
        Carga eventos usando el mismo generador de IDs que el proceso Offline.
    """
    print(f"\n--- Paso 3: Cargando {len(eventos_relevantes)} eventos en BD ---")
    
    eventos_creados = 0
    eventos_actualizados = 0
    
    for evento in eventos_relevantes:
        try:
            # Usamos MD5 para ser consistentes con el histórico
            google_id = generar_id_unico(
                evento['timestamp'],
                evento['usuario'],
                evento['archivo_id'],
                evento['accion']
            )

            obj, created = EventoDeAcceso.objects.update_or_create(
                id_evento_google = google_id, # Usamos el ID único
                defaults={
                    'timestamp': evento['timestamp'],
                    'email_usuario': evento['usuario'],
                    'archivo_id': evento['archivo_id'],
                    'nombre_archivo': evento['archivo_titulo'],
                    'tipo_evento': evento['accion'],
                    'direccion_ip': evento['ip'],
                    'detalles': evento.get('detalles_json', {}),
                }
            )
            
            if created:
                eventos_creados += 1
            else:
                eventos_actualizados += 1
        
        except Exception as e:
            if "direccion_ip" in str(e):
                 # Reintento con IP neutra si falla la validacion
                 try:
                    EventoDeAcceso.objects.update_or_create(
                        id_evento_google=google_id,
                        defaults={
                            'timestamp': evento['timestamp'],
                            'email_usuario': evento['usuario'],
                            'archivo_id': evento['archivo_id'],
                            'nombre_archivo': evento['archivo_titulo'],
                            'tipo_evento': evento['accion'],
                            'direccion_ip': '0.0.0.0', 
                            'detalles': evento.get('detalles_json', {}),
                        }
                    )
                 except:
                     pass

    print(f"✓ Carga a BD completada.")
    print(f"  -> Nuevos: {eventos_creados} | Actualizados: {eventos_actualizados}")

# --- BACKUP COMPLETO ---

def guardar_reporte_json_desde_bd():
    """
        Exporta TODOS los eventos (Históricos + Nuevos) a un solo JSON consolidado.
    """
    try:
        base_dir = Path(settings.BASE_DIR)
        cache_dir = base_dir / 'cache_sgsi'
        report_path = cache_dir / 'reporte_historico.json'

        cache_dir.mkdir(parents=True, exist_ok= True)

        print(f"\n📁 Generando Backup Consolidado en: {report_path}")

        # Obtenemos TODO para no perder historia
        eventos_db = EventoDeAcceso.objects.all().order_by('-timestamp').values()

        eventos_list = []
        for evento in eventos_db:
            ts = evento['timestamp']
            hora_fmt = ts.strftime("%d/%m/%Y %I:%M %p") if ts else "N/A"

            eventos_list.append({
                "hora": hora_fmt, 
                "usuario": evento['email_usuario'],
                "accion": evento['tipo_evento'],
                "archivo": f"{evento['nombre_archivo']} ({evento['archivo_id']})",
                "ip": evento['direccion_ip']
            })
        
        archivo_ids = set(e['archivo_id'] for e in eventos_db if e['archivo_id'])

        reporte = {
            'periodo_dias': "HISTORICO_COMPLETO",
            'fecha_consulta': datetime.now(timezone.utc).isoformat(),
            'total_eventos_procesados': len(eventos_list),
            'eventos_relevantes': len(eventos_list),
            'archivos_monitoreados': len(archivo_ids),
            'eventos': eventos_list
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent= 2, ensure_ascii=False)

        print(f"✓ Backup actualizado: {len(eventos_list)} eventos totales.")
        return True

    except Exception as e:
        print(f"Error guardando reporte JSON {e}")
        return False

def refrescar_token_google():
    try:
        base_dir = Path(settings.BASE_DIR)
        cache_file = base_dir / 'cache_sgsi' / 'inventory_cache'

        if not cache_file.exists(): return True

        with open(cache_file, 'rb') as f:
            cache_data = pickle.load(f)
        
        age_hours = (datetime.now() - cache_data.get('timestamp')).total_seconds() / 3600

        if age_hours >= CACHE_EXPIRY_HOURS:
            cache_file.unlink()
            print(f"Token caducado eliminado (edad: {age_hours:.1f} hours)")

        return True
    except:
        return True

# ============================================================================
# CLASE GoogleDriveCollector (NUEVA - para usar en views.py)
# ============================================================================

class GoogleDriveCollector:
    """Clase wrapper para usar desde views.py"""
    def __init__(self):
        self.credentials = None
        
    def obtener_eventos(self):
        # Reutilizamos la lógica del comando, pero retornando la lista
        # Nota: Por simplicidad, instanciamos el comando para ejecutar su logica central
        # o llamamos a las funciones directamente.

        refrescar_token_google()
        creds = autenticar_cuenta_servicio()
        if not creds: return []
        
        cached = cargar_inventario_cache()
        if cached:
            t_ids, _ = cached
        else:
            svc = build('drive', 'v3', credentials=creds)
            t_ids, count = lista_ids_archivos_optimizado(svc, TARGET_FOLDER_ID)
            guardar_inventario_cache(t_ids, count)

        start_iso = (datetime.now(timezone.utc) - timedelta(days=DIAS_A_CONSULTAR)).isoformat()
        evs, _ = consultar_auditoria_optimizado(creds, start_iso, t_ids)
        
        return evs

class Command(BaseCommand):
    help = 'Ejecuta el ETL Online (Recolección en tiempo real)'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("INICIANDO RECOLECCIÓN REAL (ONLINE)"))
        
        # 1. Autenticación
        print("\n📌 Verificando token de autenticación...")
        refrescar_token_google()
        credentials = autenticar_cuenta_servicio()
        
        if not credentials:
            self.stderr.write("Error de credenciales. Abortando.")
            return

        # 2. Inventario
        self.stdout.write('\n--- Paso 1: Inventario ---')
        cached = cargar_inventario_cache()
        
        if cached:
            t_ids, count = cached
        else:
            # Si no hay cache, buscamos en la API
            svc = build('drive', 'v3', credentials=credentials)
            t_ids, count = lista_ids_archivos_optimizado(svc, TARGET_FOLDER_ID)
            guardar_inventario_cache(t_ids, count)
        
        print(f"  -> Archivos a monitorear: {len(t_ids)}")

        # 3. Auditoría
        self.stdout.write('\n--- Paso 2: Auditoría ---')
        # Calculamos la fecha de inicio (hace 30 días)
        start_iso = (datetime.now(timezone.utc) - timedelta(days=DIAS_A_CONSULTAR)).isoformat()
        
        # Llamamos a la función de consulta
        eventos, total_procesados = consultar_auditoria_optimizado(credentials, start_iso, t_ids)

        # 4. Carga a BD
        if eventos:
            guardar_eventos_en_db(eventos)
        else:
            print("  No hay eventos relevantes nuevos para guardar.")

        # 5. Backup Automático
        print("\n📁 Actualizando Backup Consolidado (Full Snapshot)...")
        guardar_reporte_json_desde_bd()

        self.stdout.write(self.style.SUCCESS("\n✓ PROCESO ONLINE FINALIZADO"))