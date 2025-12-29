from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone

# Importamos Modelos
from .models import EventoDeAcceso

# --- IMPORTANTE: Reutilizamos la lógica probada del Sprint 2 ---
# Esto evita duplicar código y errores de inconsistencia en la BD
try:
    from .management.commands.recolectar_eventos_reales import GoogleDriveCollector, guardar_eventos_en_db
except ImportError:
    GoogleDriveCollector = None
    guardar_eventos_en_db = None

# --- INTEGRACION CON SPRINT 5 (IA) ---
try:
    # Importamos la función real que creamos en analisis.py
    from .analisis import ejecutar_deteccion_anomalias
except ImportError:
    # Fallback por si acaso, pero debería existir
    def ejecutar_deteccion_anomalias(): return 0

# --- VISTAS ---

@login_required
def dashboard_anomalias(request):
    """Redirección para mantener compatibilidad"""
    return redirect('monitoreo:dashboard-v2')

@login_required
def dashboard_monitoreo(request):
    """
       Dashboard completo de monitoreo con estadísticas, filtros y paginación.
    """
    #1.  Obtener parámetros de filtro
    filtro_anomalia = request.GET.get('anomalia', '')
    filtro_tipo = request.GET.get('tipo', '')
    filtro_usuario = request.GET.get('usuario', '')
    busqueda_q = request.GET.get('q', '')

    # 2. QuerySet Base (Ordenado por fecha)
    eventos = EventoDeAcceso.objects.all().order_by('-timestamp')

    # 3. Aplicar Filtros Dinámicos (ACTUALIZADO SPRINT 5)
    if filtro_anomalia:
        if filtro_anomalia == 'no':
            # Mostrar solo normales
            eventos = eventos.filter(es_anomalia=False)

        elif filtro_anomalia == 'si':
            # Mostrar TODAS las anomalias (cualquier severidad)
            eventos = eventos.filter(es_anomalia=True)

        elif filtro_anomalia in ['CRITICA', 'ALTA', 'MEDIA']:
            # Mostrar solo una severidad especifica
            eventos = eventos.filter(severidad=filtro_anomalia)

    if filtro_tipo:
        eventos = eventos.filter(tipo_evento=filtro_tipo)

    if filtro_usuario:
        eventos = eventos.filter(email_usuario__icontains=filtro_usuario)

    # Filtro de Búsqueda General (El Q object)
    if busqueda_q:
        eventos = eventos.filter(
            Q(email_usuario__icontains=busqueda_q) |
            Q(nombre_archivo__icontains=busqueda_q) |
            Q(direccion_ip__icontains=busqueda_q)
        )
    
    #4. Calcular estadísticas (KPIs)
    total_eventos = EventoDeAcceso.objects.count()
    qs_anomalias = EventoDeAcceso.objects.filter(es_anomalia=True)
    total_anomalias = qs_anomalias.count()

    eventos_normales = total_eventos - total_anomalias

    # KPI Amarillo: Anomalías de alto riesgo
    anomalias_criticas = qs_anomalias.filter(severidad__in=['ALTA', 'CRITICA']).count()

    # 5. Tabla de "Últimas Anomalías"
    anomalias_recientes = qs_anomalias.order_by('-timestamp')[:10]

    #6. Paginación
    paginator = Paginator(eventos, 20) # 20 eventos por pagina para mejor visualizacion
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    #7. Listas para el Select de Tipos
    tipos_evento = EventoDeAcceso.objects.values_list(
        'tipo_evento', flat=True
    ).distinct().order_by('tipo_evento')

    #8. Preparar contexto para plantilla
    context = {
        'page_obj':             page_obj,               # Para la tabla principal
        'total_eventos':        total_eventos,          # KPI Azul
        'total_anomalias':      total_anomalias,        # KPI Rojo
        'eventos_normales':     eventos_normales,       # KPI Verde
        'anomalias_criticas':   anomalias_criticas,     # KPI Amarillo
        'anomalias_recientes':  anomalias_recientes,    # Tabla Pequeña roja
        'tipos_evento':         tipos_evento,           # Para el <select>
        # Mantener el estado de los filtros en la vista
        'filtro_anomalia':      filtro_anomalia,
        'filtro_tipo':          filtro_tipo,
        'filtro_usuario':       filtro_usuario,
        'busqueda_q':           busqueda_q,
    }

    return render(request, 'monitoreo/dashboard.html', context)

# --- APIs (AJAX) ---

@login_required
@require_http_methods(["POST"])
def api_sincronizar_eventos(request):
    """
        API para el botón 'Sincronizar'.
        Usa el recolector del Sprint 2/4 para mantener consistencia.
    """
    if not GoogleDriveCollector:
        return JsonResponse({'success': False, 'message': 'Error: Collector no encontrado'}, status=500)

    try:
        # 1. Instanciar Recolector
        collector = GoogleDriveCollector()

        # 2. Obtener eventos crudos de Google
        eventos_raw = collector.obtener_eventos()

        if not eventos_raw:
            return JsonResponse({
                'success': True,
                'mensaje': 'Sincronización completada. No se encontraron eventos nuevos.',
                'nuevos': 0,
            })
        
        # 3. Guardar en BD (Reutilizando lógica del Sprint 2)
        count_inicio = EventoDeAcceso.objects.count()
        guardar_eventos_en_db(eventos_raw)
        count_fin = EventoDeAcceso.objects.count()

        nuevos = count_fin - count_inicio

        return JsonResponse({
            'success': True,
            'mensaje': f'Sincronización exitosa. {nuevos} eventos nuevos registrados.',
        })
    
    except Exception as e:
        # Log del error en la consola para debugging
        print(f"Error Sync API: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
@require_http_methods(["POST"])
def api_ejecutar_deteccion(request):
    """
        API para el botón 'Detectar IA'.
        Ejecuta el Isolation Forest real (Sprint 5).
    """

    try:
        # Ejecutamos la función de análisis real
        contador_anomalias = ejecutar_deteccion_anomalias()
        
        return JsonResponse({
            'success': True,
            'mensaje': f'Análisis completado. Se detectaron/actualizaron {contador_anomalias} anomalías.'
        })
    except Exception as e:
        # Si algo falla (ej: falta memoria, error de sklearn), lo reportamos al frontend
        return JsonResponse({'success': False, 'mensaje': f'Error en IA: {str(e)}'}, status=500)