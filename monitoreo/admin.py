from django.contrib import admin
from django.utils.html import format_html
from .models import EventoDeAcceso

@admin.register(EventoDeAcceso)
class EventoDeAccesoAdmin(admin.ModelAdmin):
    """
        ADMIN CONFIG PARA EventoDeAcceso - SPRINT 2
    
        Features:
        ✅ Lista optimizada (mostrar campos clave)
        ✅ Filtros por es_anomalia, tipo_evento, timestamp
        ✅ Búsqueda por email y nombre_archivo
        ✅ readonly_fields (proteger datos históricos)
        ✅ date_hierarchy (navegación por fechas)
        ✅ Fieldsets organizados
        ✅ Permisos (sin agregar, sin borrar)
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
    ]

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
        'es_anomalia',
        'detalles',
        'timestamp_formateado',  # Método personalizado
    ]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # NAVEGACIÓN POR FECHAS - Facilita navegar por timeline
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    date_hierarchy = 'timestamp'

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # FIELDSETS - Cómo se agrupan los campos en el detalle
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    fieldsets = (
        ('Información del Usuario', {
            'fields': ('email_usuario', 'direccion_ip'),
            'description': 'Quién accedió y desde dónde',
        }),
        ('Información del Archivo', {
            'fields': ('nombre_archivo', 'archivo_id'),
            'description': 'Qué archivo fue accedido',
        }),
        ('Información Temporal', {
            'fields': ('timestamp', 'timestamp_formateado'),
            'description': 'Cuándo ocurrió el evento',
        }),
        ('Análisis', {
            'fields': ('tipo_evento', 'es_anomalia'),
            'description': 'Tipo de evento e indicador de anomalía',
        }),
        ('Detalles JSON (Datos Crudos)', {
            'fields': ('detalles',),
            'classes': ('collapse',),  # Colapsable de inicio
            'description': 'Respuesta cruda de la API de Google Drive',
        }),
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CONFIGURACIÓN DE ACCIONES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    actions_on_top = True
    actions_on_bottom = True
    list_per_page = 50  # Mostrar 50 eventos por página

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PERMISOS - Quitar opciones de agregar/borrar
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
        """Muestra tipo de evento con ícono"""
        iconos = {
            'view': '👁️ Consultado',
            'download': '⬇️ Descargado',
            'edit': '✏️ Editado',
            'delete': '🗑️ Eliminado',
            'share': '📤 Compartido',
        }
        icono = iconos.get(obj.tipo_evento, '📄 Listado')
        return f'{icono} {obj.tipo_evento}'
    tipo_evento_display.short_description = 'Tipo Evento'

    def anomalia_badge(self, obj):
        """
        Badge verde/rojo según es_anomalia
        ✅ Verde si es normal
        🔴 Rojo si es anomalía
        """
        if obj.es_anomalia:
            return format_html(
                '<span style="background-color: #ff6b6b; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">ANOMALÍA</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #51cf66; color: white; padding: 3px 8px; border-radius: 3px;">Normal</span>'
            )
    anomalia_badge.short_description = 'Estado'
    
    def nombre_archivo_short(self, obj):
        """Trunca nombre largo a 30 caracteres"""
        if len(obj.nombre_archivo) > 30:
            return f"{obj.nombre_archivo[:27]}..."
        return obj.nombre_archivo
    nombre_archivo_short.short_description = 'Archivo'

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ORDENAMIENTO Y BÚSQUEDA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ordering = ['-timestamp']  # Más recientes primero

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # INFORMACIÓN ADICIONAL
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_queryset(self, request):
        """
        Optimizar query para evitar N+1
        Aunque en este caso no hay relaciones FK, pero buena práctica
        """
        queryset = super().get_queryset(request)
        return queryset.select_related()  # Preparado para futuras relaciones
    
    class Meta:
        model = EventoDeAcceso
        verbose_name = '📌 Evento de Acceso'
        verbose_name_plural = '📌 Eventos de Acceso'

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CONFIGURACIÓN GLOBAL DEL ADMIN
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    admin.site.site_header = '🔐 Sistema de Monitoreo SGSI'
    admin.site.site_title = 'Admin - SGSI'
    admin.site.index_title = 'Bienvenido al Panel de Administración'