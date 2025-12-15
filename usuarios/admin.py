from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from . models import UsuarioPersonalizado, Role, Permission

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion', 'fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    list_filter = ['fecha_creacion']
    readonly_fields = ['fecha_creacion']

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion', 'get_permisos_count', 'fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    filter_horizontal = ['permisos']
    list_filter = ['activo', 'fecha_creacion']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']

    def get_permisos_count(self, obj):
        """Muestra el numero de permisos asginados"""
        return obj.permisos.count()
    get_permisos_count.short_description = "# Permisos"

@admin.register(UsuarioPersonalizado)
class UsuarioPersonalizadoAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'rol', 'es_activo', 'ultima_actividad']
    list_filter = ['rol', 'es_activo', 'is_staff']
    search_fields = ['username', 'email']

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informacion del Sistema', {
            'fields': ('rol', 'es_activo', 'debe_cambiar_contrasena', 'ultimo_acceso',
                       'intentos_login')
        }),
        ('Fecha de Auditoria', {
            'fields': ('fecha_creacion', 'fecha_eliminacion')
        }),
    )

    readonly_fields = ['fecha_creacion', 'fecha_eliminacion', 'ultimo_acceso', 'intentos_login']

    def ultima_actividad(self, obj):
        return obj.ultimo_acceso or 'Nunca accedió'
    ultima_actividad.short_description = 'Ultima Actividad'