from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# ============================================================================
# MODELO: Permission (Permisos individuales)
# ============================================================================

class Permission(models.Model):
    """
        Modelo de Permisos personalizados.

        Los permisos disponibles se definen en el SIGNAL de inicialización.
    """

    nombre = models.CharField(
        max_length=50,
        unique= True,
        verbose_name= "Nombre del Permiso",
        help_text= "Identificador único del permiso (ej: view_dashboard)"
    )

    descripcion = models.TextField(
        verbose_name="Descripcion",
        help_text= "Descripcion clara de que permite este permiso"
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add = True,
        verbose_name= "Fecha de Creacion"
    )

    class Meta:
        verbose_name = "Permiso"
        verbose_name_plural = "Permisos"
        ordering = ['nombre']

        def __str__(self):
            return f"{self.nombre}"
        
        def __repr__(self):
            return f"<Permission: {self.nombre}>"
        
# ============================================================================
# MODELO: Role (Roles/Grupos)
# ============================================================================

class Role(models.Model):
    """
        Modelo de Roles de Usuario.

        Los roles agrupan permisos y se asignan a usuarios.

        Roles predefinidos (segregación de funciones ISO 27001):
            - Admin: Acceso Total
            - Auditor: Ver anomalías, descargar reportes, crear tickets
            - Viewer: Solo ver dashboard (acceso de solo lectura)
    """

    ROLE_CHOICES = [
        ('admin',   'Administrador'),
        ('auditor', 'Auditor'),
        ('viewer',  'Visualizador'),
    ]

    nombre = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        unique=True,
        verbose_name="Nombre del Rol",
    )

    descripcion = models.TextField(
        verbose_name="Descripcion",
        help_text="Descripcion clara del rol y sus responsabilidades",
    )

    permisos = models.ManyToManyField(
        Permission,
        related_name = 'roles',
        verbose_name="Permisos",
        help_text="Permisos asignados a este rol"
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Actualización"
    )

    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text="Si el rol esta activo para nuevas asignaciones"
    )

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.get_nombre_display()}"
    
    def __repr__(self):
        return f"<Role: {self.nombre}>"
    
    def tiene_permiso(self, nombre_permiso):
        """Verifica si el rol tiene un permiso especifico"""
        return self.permisos.filter(nombre=nombre_permiso).exists()
    
    def agregar_permisos(self, nombre_permiso):
        """Agrega un permiso al rol"""
        try:
            permiso = Permission.objects.get(nombre=nombre_permiso)
            self.permisos.add(permiso)
            return True
        except Permission.DoesNotExist:
            return False
    
    def remover_permiso(self, nombre_permiso):
        """Remueve un permiso del rol"""
        try:
            permiso = Permission.objects.get(nombre=nombre_permiso)
            self.permisos.remove(permiso)
            return True
        except Permission.DoesNotExist:
            return False
    
    def get_nombre_display(self):
        """Retorna el nombre legible del rol"""
        choices_dict = dict(self.ROLE_CHOICES)
        return choices_dict.get(self.nombre, self.nombre)
        
# ============================================================================
# MODELO: UsuarioPersonalizado (User + Roles)
# ============================================================================
class UsuarioPersonalizado(AbstractUser):
    """
        Modelo de usuario personalizado que extiende AbstractUser.
        Incluye campos para soft-delete y auditoría de acceso.
    """
    
    # Rol asignado
    rol = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios',
        verbose_name="Rol",
        help_text="Rol asignado al usuario"
    )

    # Timestamps (Auditoría)
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación",
        help_text="Se establece automáticamente cuando se crea el usuario"
    )
    
    fecha_eliminacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Eliminación",
        help_text="Se establece cuando el usuario es eliminado (soft-delete)"
    )
    
    # Campos adicionales de seguridad
    es_activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="¿Puede el usuario acceder al sistema?"
    )

    debe_cambiar_contrasena = models.BooleanField(
        default=False,
        verbose_name="Debe Cambiar Contraseña",
        help_text="¿Fuerza al usuario a cambiar su contraseña en el próximo inicio de sesión?"
    )

    ultimo_acceso = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Último Acceso",
        help_text="Marca de tiempo del último acceso al sistema"
    )

    intentos_login = models.IntegerField(
        default=0,
        verbose_name="Intentos de Login Fallidos",
        help_text="Contador de intentos fallidos (se resetea con login exitoso)"
    )

    class Meta:
        verbose_name = "Usuario Personalizado"
        verbose_name_plural = "Usuarios Personalizados"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['rol']),
            models.Index(fields=['es_activo']),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_nombre_rol_display() if self.rol else 'Sin Rol'})"
    
    def __repr__(self):
        return f"<UsuarioPersonalizado: {self.username}>"
    
    def get_nombre_rol_display(self):
        """Retorna el nombre legible del rol asignado"""
        if self.rol:
            return self.rol.get_nombre_display()
        return "Sin Rol"
    
     # ========== MÉTODOS SOFT-DELETE ==========
    
    def soft_delete(self):
        """Marca el usuario como eliminado sin borrar del DB (soft-delete)"""
        self.fecha_eliminacion = timezone.now()
        self.es_activo = False
        self.is_active = False
        self.save()
    
    def restore(self):
        """Restaura un usuario eliminado (soft-delete reverso)"""
        self.fecha_eliminacion = None
        self.is_active = True
        self.es_activo = True
        self.save()
    
    @property
    def esta_eliminado(self):
        """Retorna True si el usuario fue eliminado"""
        return self.fecha_eliminacion is not None
    
# ========== MÉTODOS DE PERMISOS ==========

    def tiene_permiso(self, nombre_permiso):
        """
             Verifica si el usuario tiene un permiso específico.
        
            Args:
                nombre_permiso (str): Nombre del permiso a verificar
                
            Returns:
                bool: True si el usuario tiene el permiso, False en caso contrario
        """
        if not self.rol or not self.es_activo:
            return False
        
        return self.rol.tiene_permiso(nombre_permiso)
    
    def es_admin(self):
        """¿El usuario es administrador?"""
        return self.rol and self.rol.nombre == 'admin'
    
    def es_auditor(self):
        """¿El usuario es auditor?"""
        return self.rol and self.rol.nombre == 'auditor'
    
    def es_visualizador(self):
        """¿El usuario es visualizador?"""
        return self.rol and self.rol.nombre == 'viewer'
    
    def puede_ver_dashboard(self):
        """¿El usuario puede ver el dashboard?"""
        return self.tiene_permiso('view_dashboard')
    
    def puede_ver_anomalias(self):
        """¿El usuario puede ver las anomalias?"""
        return self.tiene_permiso('view_anomalies')
    
    def puede_descargar_reportes(self):
        """¿El usuario puede descargar reportes?"""
        return self.tiene_permiso('download_report')
    
    def puede_crear_ticket(self):
        """¿El usuario puede crear tickets en GLPI?"""
        return self.tiene_permiso('create_ticket')
    
    def puede_gestionar_usuarios(self):
        """¿El usuario puede gestionar otros usuarios?"""
        return self.tiene_permiso('manage_users')
    
    # ========== MÉTODOS DE AUDITORÍA ==========

    def registrar_acceso(self):
        """Registra que el usuario ha accedido al sistema"""
        self.ultimo_acceso = timezone.now()
        self.intentos_login = 0  # Resetea intentos fallidos tras acceso exitoso
        self.save()

    def registrar_intento_fallido(self):
        """Registra un intento fallido de login"""
        self.intentos_login += 1
        self.save()

        # Bloqueo automático tras 5 intentos fallidos
        if self.intentos_login >= 5:
            self.es_activo = False
            self.save()
            return False
        return True
    
    def resetear_intentos_fallido(self):
        """Resetea el contador de intentos fallidos tras un login exitoso"""
        self.intentos_login = 0
        self.save()

# ============================================================================
# SIGNAL: Crear datos iniciales (Roles y Permisos)
# ============================================================================

@receiver(post_migrate)
def crear_roles_y_permisos_iniciales(sender, **kwargs):
    """
        Crea los roles y permisos iniciales después de las migraciones.
    
        Se ejecuta automáticamente después de `python manage.py migrate`
    """
    
    # Solo ejecutar para la app 'usuarios'
    if sender.name != 'usuarios':
        return
    
    print("Creando permisos y roles iniciales...")
    
    # Crear permisos si no existen
    permisos_data = {
        'view_dashboard': 'Ver dashboard principal del sistema',
        'view_anomalies': 'Ver listado de anomalías detectadas',
        'view_events': 'Ver eventos de acceso en Google Drive',
        'create_ticket': 'Crear tickets en GLPI automáticamente',
        'edit_anomaly': 'Editar estado y clasificación de anomalías',
        'download_report': 'Descargar reportes PDF y Excel',
        'manage_users': 'Crear, editar, eliminar usuarios',
        'manage_roles': 'Crear y editar roles con permisos',
        'configure_alerts': 'Configurar alertas y notificaciones',
        'admin_access': 'Acceso completo a todas las funciones',
    }
    
    permisos_creados = {}
    for nombre, descripcion in permisos_data.items():
        permiso, created = Permission.objects.get_or_create(
            nombre=nombre,
            defaults={'descripcion': descripcion}
        )
        permisos_creados[nombre] = permiso
        if created:
            print(f"Permiso '{nombre}' creado")
        else:
            print(f"Permiso '{nombre}' ya existe")
    
    # Crear roles si no existen
    
    # ADMIN
    role_admin, created = Role.objects.get_or_create(
        nombre='admin',
        defaults={
            'descripcion': 'Administrador del sistema con acceso completo',
            'activo': True
        }
    )
    
    admin_permisos = [
            permisos_creados['view_dashboard'],
            permisos_creados['view_anomalies'],
            permisos_creados['view_events'],
            permisos_creados['create_ticket'],
            permisos_creados['edit_anomaly'],
            permisos_creados['download_report'],
            permisos_creados['manage_users'],
            permisos_creados['manage_roles'],
            permisos_creados['configure_alerts'],
            permisos_creados['admin_access'],
    ]
    role_admin.permisos.set(admin_permisos)

    if created:
        print("Rol 'Admin' CREADO con 10 permisos")
    else:
        print("Rol 'Admin' ACTUALIZADO con 10 permisos")
    
    # AUDITOR
    role_auditor, created = Role.objects.get_or_create(
        nombre='auditor',
        defaults={
            'descripcion': 'Auditor de seguridad - puede ver anomalías y crear tickets',
            'activo': True
        }
    )

    auditor_permisos = [
            permisos_creados['view_dashboard'],
            permisos_creados['view_anomalies'],
            permisos_creados['view_events'],
            permisos_creados['create_ticket'],
            permisos_creados['edit_anomaly'],
            permisos_creados['download_report'],
            permisos_creados['configure_alerts'],
    ]
    role_auditor.permisos.set(auditor_permisos)

    if created:
        print("Rol 'Auditor' CREADO con 7 permisos")
    else:
        print("Rol 'Auditor' ACTUALIZADO con 7 permisos")
    
    # VIEWER
    role_viewer, created = Role.objects.get_or_create(
        nombre='viewer',
        defaults={
            'descripcion': 'Solo visualización - acceso de solo lectura',
            'activo': True
        }
    )

    viewer_permisos =[
        permisos_creados['view_dashboard'],
        permisos_creados['view_anomalies'],
        permisos_creados['download_report'],
    ]
    role_viewer.permisos.set(viewer_permisos)

    if created:
        print("Rol 'Viewer' CREADO con 3 permisos")
    else:
        print("Rol 'Viewer' ACTUALIZADO con 3 permisos")
    
    print("Permisos y roles iniciales configurados")
