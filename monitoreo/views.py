from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from datetime import datetime
from .models import EventoDeAcceso
from .management.commands.recolectar_eventos_reales import GoogleDriveCollector
from .analisis import ejecutar_deteccion_anomalias

def limpiar_evento_para_json(evento):
    """
    Convierte objetos datetime a strings para que sean JSON serializable.
    Recorre recursivamente el diccionario y convierte cualquier datetime a ISO string.
    """
    if isinstance(evento, dict):
        return {k: limpiar_evento_para_json(v) for k, v in evento.items()}
    elif isinstance(evento, list):
        return [limpiar_evento_para_json(item) for item in evento]
    elif isinstance(evento, datetime):
        return evento.isoformat()
    else:
        return evento


@login_required
def dashboard_anomalias(request):
    # Buscamos en la BD solo los eventos marcados como anomalias (es_anomalias=True)
    anomalias = EventoDeAcceso.objects.filter(es_anomalia=True)

    context={
        'anomalias': anomalias,
        'total_anomalias': anomalias.count(),
    }

    # Renderizamos la plantilla HTML con los datos de anomalias
    return render(request, 'monitoreo/dashboard.html', context)

@login_required
def dashboard_monitoreo(request):
    """
        Dashboard completo de monitoreo con estadísticas, filtros y paginación.

        Parámetros GET:
        - anomalia: 'si' / 'no' / '' (todos)
        - tipo: tipo de evento para filtrar
        - usuario: email de usuario para filtrar
        - page: número de página
    """

    #1.  Obtener parámetros de filtro desde GET
    filtro_anomalia = request.GET.get('anomalia', '')
    filtro_tipo = request.GET.get('tipo', '')
    filtro_usuario = request.GET.get('usuario', '')

    # 2. Construir QuerySet base
    eventos = EventoDeAcceso.objects.all().order_by('-timestamp')

    #3. Aplicar Filtros
    if filtro_anomalia == 'si':
        eventos = eventos.filter(es_anomalia=True)
    elif filtro_anomalia == 'no':
        eventos = eventos.filter(es_anomalia=False)

    if filtro_tipo:
        eventos = eventos.filter(tipo_evento=filtro_tipo)

    if filtro_usuario:
        eventos = eventos.filter(email_usuario__icontains=filtro_usuario)
    
    #4. Calcular estadisticas
    total_eventos = EventoDeAcceso.objects.count()
    anomalias = EventoDeAcceso.objects.filter(es_anomalia=True)
    total_anomalias = anomalias.count()
    anomalias_criticas = anomalias.count() # TODO: implementar severidad futura

    #5. Obtener ultimas anomalias
    anomalias_recientes = EventoDeAcceso.objects.filter(
        es_anomalia=True
    ).order_by('-timestamp')[:20]

    #6. Aplicar Paginacion
    paginator = Paginator(eventos, 50) # 20 eventos por pagina
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    #7. Obtener lista de tipos unicos para busqueda de filtro
    tipos_evento = EventoDeAcceso.objects.values_list(
        'tipo_evento', flat=True
    ).distinct().order_by('tipo_evento')

    #8. Preparar contexto para plantilla
    context = {
        'total_eventos':        total_eventos,
        'total_anomalias':      total_anomalias,
        'anomalias_criticas':   anomalias_criticas,
        'anomalias_recientes':  anomalias_recientes,
        'page_obj':             page_obj,
        'tipos_eventos':        tipos_evento,
        'filtro_anomalia':      filtro_anomalia,
        'filtro_tipo':          filtro_tipo,
        'filtro_usuario':       filtro_usuario,
    }

    return render(request, 'monitoreo/dashboard.html', context)

@login_required
@require_http_methods(["POST"])
def api_sincronizar_eventos(request):
    """
    API: Sincroniza eventos desde Google Drive Activity API a BD.
    """
    try:
        collector = GoogleDriveCollector()
        eventos_raw = collector.obtener_eventos()

        if not eventos_raw:
            return JsonResponse({
                'success': True,
                'mensaje': 'Sin cambios - No hay nuevos eventos para sincronizar',
                'eventos_procesados': 0,
                'eventos_nuevos': 0,
                'eventos_duplicados': 0
            }, status=200)
        
        eventos_nuevos = 0
        eventos_duplicados = 0

        for evento_raw in eventos_raw:
            evento_id = evento_raw.get('archivo_id', 'unknown')

            try:
                # El timestamp YA viene como datetime desde recolectar_eventos_reales.py
                timestamp = evento_raw.get('timestamp')
                
                # Si aún es None, usar ahora
                if timestamp is None:
                    from django.utils import timezone
                    timestamp = timezone.now()
                    print(f"⚠️ Timestamp nulo para evento {evento_id}, usando ahora: {timestamp}")

                # Serializar evento para JSON
                evento_raw_serializable = limpiar_evento_para_json(evento_raw)

                # Crear una clave única combinando archivo_id + usuario + timestamp + acción
                evento_unico_id = f"{evento_raw.get('archivo_id')}_{evento_raw.get('usuario')}_{timestamp}_{evento_raw.get('accion')}"

                evento, created = EventoDeAcceso.objects.get_or_create(
                    archivo_id=evento_id,
                    email_usuario=evento_raw.get('usuario', 'desconocido@google.com'),
                    timestamp=timestamp,
                    tipo_evento=evento_raw.get('accion', 'unknown'),
                    defaults={
                        'direccion_ip': evento_raw.get('ip', '0.0.0.0'),
                        'nombre_archivo': evento_raw.get('archivo_titulo', 'sin nombre'),
                        'es_anomalia': False,
                        'detalles': evento_raw_serializable,
                    }
                )

                
                if created:
                    eventos_nuevos += 1
                else:
                    eventos_duplicados += 1
                    
            except Exception as e:
                print(f"❌ Error guardando evento {evento_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        mensaje = f'✅ Sincronización completada: {eventos_nuevos} eventos nuevos guardados'
        if eventos_duplicados > 0:
            mensaje += f', {eventos_duplicados} duplicados ignorados'
            
        return JsonResponse({
            'success': True,
            'eventos_nuevos': eventos_nuevos,
            'eventos_duplicados': eventos_duplicados,
            'total_eventos': len(eventos_raw),
            'mensaje': mensaje,
            'eventos_procesados': eventos_nuevos
        }, status=200)

    except Exception as e:
        import traceback
        error_msg = f"Error en sincronización: {str(e)}"
        print(f"❌ TRACEBACK: {traceback.format_exc()}")

        return JsonResponse({
            'success': False,
            'error': error_msg,
            'mensaje': 'Error durante la sincronización. Revisa los logs.',
            'eventos_procesados': 0
        }, status=500)


    
@login_required
@require_http_methods(["POST"])
def api_ejecutar_deteccion(request):
    """
        API: Ejecuta detección de anomalías usando Isolation Forest.
    
        Retorna:
        {
            'success': True/False,
            'anomalias_detectadas': int,
            'eventos_procesados': int,
            'mensaje': str,
            'error': str (si hay error)
        }
    """

    try:
        #1. Ejecutar funcion de deteccion (usa la funcion ejecutar_deteccion_anomalias)
        contador_anomalias = ejecutar_deteccion_anomalias()

        #2. Contar Eventos procesados
        eventos_procesados = EventoDeAcceso.objects.count()

        #3. Retornar Resultados
        return JsonResponse({
            'success': True,
            'anomalias_detectadas': contador_anomalias,
            'eventos_procesados': eventos_procesados,
            'mensaje': f'✅ Detección completada. {contador_anomalias} anomalías detectadas.'
        })
    
    except Exception as e:
        import traceback
        error_msg = f"Error en detección: {str(e)}"
        print(f"TRACEBACK: {traceback.format_exc()}")
        
        return JsonResponse({
            'success': False,
            'error': error_msg,
            'mensaje': 'Error durante la detección'
        }, status=500)