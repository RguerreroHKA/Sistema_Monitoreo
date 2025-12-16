import json
from django.contrib import admin
from django.utils.html import format_html
from .models import EventoDeAcceso

@admin.register(EventoDeAcceso)
class EventoDeAccesoAdmin(admin.ModelAdmin):
    """
        ADMIN CONFIG PARA EventoDeAcceso - SPRINT 2 (FINAL)
    """

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TABLA PRINCIPAL - Qué se ve en el listado
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    list_display = [
        'timestamp_display',
        'email_usuario',
        'tipo_evento_display',
        'anomalia_badge',
        'nombre_archivo_short',
        'direccion_ip',
    ]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FILTROS - Cómo filtrar datos
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    list_filter = [
        'es_anomalia',           # Solo anomalías / solo normales
        'tipo_evento',           # Filtrar por tipo (view, download, edit)
        'timestamp',             # Filtrar por rango de fechas
    ]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BÚSQUEDA - Campos donde buscar
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    search_fields = [
        'email_usuario',         # ✅ Buscar por email
        'nombre_archivo',        # ✅ Buscar por nombre archivo
        'archivo_id',            # ✅ Buscar por ID de archivo
        'direccion_ip',          # ✅ Buscar por IP
        'id_evento_google',
    ]

    ordering = ['-timestamp']

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CAMPOS SOLO LECTURA - No se pueden editar
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    readonly_fields = [
        'email_usuario',
        'direccion_ip',
        'timestamp',
        'archivo_id',
        'nombre_archivo',
        'tipo_evento',
        'tipo_evento_display',
        'es_anomalia',
        #'detalles',
        'json_bonito',
        'timestamp_formateado',  # Método personalizado
        'id_evento_google',
    ]

    date_hierarchy = 'timestamp'

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FIELDSETS - Cómo se agrupan los campos en el detalle
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    fieldsets = (
        ('Identificación del Evento', {
            'fields': ('id_evento_google', 'timestamp_formateado', 'tipo_evento_display'),
        }),
        ('Información del Usuario', {
            'fields': ('email_usuario', 'direccion_ip'),
            'description': 'Quién accedió y desde dónde (IP N/A indica procesos de sistema o sincronización)',
        }),
        ('Información del Archivo', {
            'fields': ('nombre_archivo', 'archivo_id'),
            'description': 'Qué archivo fue accedido',
        }),
        ('Análisis de Seguridad', {
            'fields': ('es_anomalia',),
            'description': 'Indicadores de riesgo detectados',
        }),
        ('Evidencia Forense (JSON Crudo)', {
            'fields': ('json_bonito',),
            'classes': ('collapse',),  # Colapsable de inicio
            'description': 'Datos originales inmutables recibidos de Google Drive API',
        }),
    )

    actions_on_top = True
    actions_on_bottom = True
    list_per_page = 50  # Mostrar 50 eventos por página

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PERMISOS 
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def has_add_permission(self, request):
        """
        NO PERMITIR agregar eventos manualmente
        Los eventos se crean SOLO desde recolectar_eventos_reales.py
        """
        return False
    
    def has_delete_permission(self, request, obj=None):
        """
        NO PERMITIR borrar eventos
        Son datos históricos - deben conservarse
        """
        return False
    
    def has_change_permission(self, request, obj=None):
        """
        PERMITIR cambiar (ver en detalle), pero todos fields son readonly
        """
        return True
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # MÉTODOS PERSONALIZADOS - Formateo y displays
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def timestamp_display(self, obj):
        """Muestra timestamp con formato amigable"""
        return obj.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    timestamp_display.short_description = 'Fecha/Hora'

    def timestamp_formateado(self, obj):
        """Campo readonly en detalle con formato bonito"""
        return obj.timestamp.strftime('%d de %B de %Y a las %H:%M:%S')
    timestamp_formateado.short_description = 'Fecha y Hora Formateada'

    def tipo_evento_display(self, obj):
        """
            Muestra solo el texto en español con el icono.
            Si el evento no está en el diccionario, muestra el original.
        """
        iconos = {
            'view': '👁️ Consultado',
            'download': '⬇️ Descargado',
            'edit': '✏️ Editado',
            'delete': '🗑️ Eliminado',
            'share': '📤 Compartido',
            'create': '✨ Creado',
            'move': '🚚 Movido',
            'rename': '🏷️ Renombrado',
            'upload': '⬆️ Subido',
            'print': '🖨️ Impreso',
            'access_item_content': '📄 Contenido Accedido',
            'change_user_access': '📄 Cambio de Acceso de Usuario',
            'source_copy': '📄 Se copió',
            'sync_item_content': '⬇️ Se sincronizó el contenido',
            'request_access': '✋ Solicitud Acceso',
            'deny_access_request': '🚫 Acceso Denegado',
            'add_lock': '🔒 Archivo Bloqueado',
            'remove_lock': '🔓 Archivo Desbloqueado',
        }
        # Devuelve el valor del diccionario. Si no existe, devuelve el evento original
        return iconos.get(obj.tipo_evento, f'📄 {obj.tipo_evento}')
    
    tipo_evento_display.short_description = 'Acción'

    def anomalia_badge(self, obj):
        """
        Badge verde/rojo según es_anomalia
        ✅ Verde si es normal
        🔴 Rojo si es anomalía
        """
        if obj.es_anomalia:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 4px 10px; border-radius: 15px; font-weight: bold; font-size: 12px;">⚠️ ANOMALÍA</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 4px 10px; border-radius: 15px; font-size: 12px;">Normal</span>'
            )
    anomalia_badge.short_description = 'Estado'
    
    def nombre_archivo_short(self, obj):
        """Trunca nombre largo a 30 caracteres"""
        if obj.nombre_archivo and len(obj.nombre_archivo) > 40:
            return f"{obj.nombre_archivo[:37]}..."
        return obj.nombre_archivo
    nombre_archivo_short.short_description = 'Archivo'

    def json_bonito(self, obj):
        """Formatea el JSON para que sea legible"""
        if not obj.detalles:
            return "_"
        
        # Convertimos a string con indentacion
        json_str = json.dumps(obj.detalles, indent=4, sort_keys=True)

        # Estilos CCS para que parezca un editor de codigo oscuro
        style = """
            background-color: #2b2b2b; 
            color: #a9b7c6; 
            padding: 15px; 
            border-radius: 8px; 
            font-family: 'Consolas', 'Monaco', monospace; 
            font-size: 12px;
            white-space: pre-wrap;
            border: 1px solid #444;
        """

        # Django escapará el contenido de forma segura y no intentará interpretar el JSON
        return format_html('<pre style="{}">{}</pre>', style, json_str)
    
    json_bonito.short_description = 'Evidencia JSON'

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CONFIGURACIÓN GLOBAL DEL ADMIN
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    admin.site.site_header = '🔐 Sistema de Monitoreo SGSI'
    admin.site.site_title = 'Admin - SGSI'
    admin.site.index_title = 'Bienvenido al Panel de Administración'