from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import UsuarioPersonalizado, Role, Permission

class ModuloUsuariosTestCase(TestCase):

    def setUp(self):
        # Cliente de prueba
        self.client = Client()

        # Obtenemos los roles que EL SIGNAL YA CREO automaticamente
        self.rol_admin = Role.objects.get(nombre = 'admin')
        self.rol_auditor = Role.objects.get(nombre = 'auditor')
        self.rol_viewer = Role.objects.get(nombre = 'viewer')

        # Crear superusuario
        self.superuser = UsuarioPersonalizado.objects.create_superuser(
            username="root_test", email="root@test.com", password="root123"
        )

        # Crear usuarios, Admin - Con Rol
        self.admin = UsuarioPersonalizado.objects.create_user(
            username="admin_test", email="admin@test.com", password="admin123", rol=self.rol_admin
        )

        # Crear usuario, Auditor - Con Rol
        self.auditor = UsuarioPersonalizado.objects.create_user(
            username="auditor_test", email="auditor@test.com", password="auditor123", rol=self.rol_auditor
        )

        # Crear usuario normal (sin rol, o con rol viewer por defecto si la logica lo aplica)
        self.usuario_normal = UsuarioPersonalizado.objects.create_user(
            username="user_test", email="user@test.com", password="user123", rol = self.rol_viewer
        )

    # === 1. Registro y Login ===
    def test_regirstro_y_login(self):
        # Registro de nuevo usuario
        response = self.client.post(reverse("usuarios:registro"), {
            "username": "nuevo_usuario",
            "email": "nuevo@test.com",
            "password1": "Testpass123",
            "password2": "Testpass123"
        })
        self.assertEqual(response.status_code, 302) # Redirección después del registro
        self.assertTrue(UsuarioPersonalizado.objects.filter(username="nuevo_usuario").exists())

        # Login Valido
        login = self.client.login(username="nuevo_usuario", password="Testpass123")
        self.assertTrue(login)

        # Login Inválido
        login_fail = self.client.login(username="nuevo_usuario", password="wrongpass")
        self.assertFalse(login_fail) # Redirige al login

    def test_restriccion_home_sin_login(self):  
        response = self.client.get(reverse("usuarios:home"))
        self.assertEqual(response.status_code, 302) # Redirige al login

    # === 2. Roles y Grupos ===
    def test_acceso_admin_vs_otro(self):
        # Admin accede
        self.client.force_login(self.admin)
        response = self.client.get(reverse("usuarios:lista_usuarios"))
        self.assertEqual(response.status_code, 200) 

        # Auditor intenta acceder -> Rechazado
        # CORRECCIÓN: Django redirige al login (302) por defecto, no lanza 403
        self.client.logout()
        self.client.login(username="auditor_test", password="auditor123")
        response = self.client.get(reverse("usuarios:lista_usuarios"))
        self.assertEqual(response.status_code, 302) # Redirige al login porque no pasa el test

        # Usuario sin grupo rechazado
        self.client.logout()
        self.client.login(username="user_test", password= "user123")
        response = self.client.get(reverse("usuarios:lista_usuarios"))
        self.assertEqual(response.status_code,302)

    def test_asignacion_roles_en_creacion(self):
        """Verificar que se puede asignar un rol al crear usuario"""
        self.client.login(username="admin_test", password="admin123")
        response = self.client.post(reverse("usuarios:crear_usuario"), {
            "username": "usuario_con_rol",
            "email": "conrol@test.com",
            "password1": "Testpass123",
            "password2": "Testpass123",
            "rol": self.rol_auditor.id  # ✅ CORRECCIÓN: Campo 'rol' es obligatorio
        })

        # Si falla (200), imprimimos errores del form
        if response.status_code == 200:
            print("Errores form creacion:", response.context['form'].errors)
        
        self.assertEqual(response.status_code, 302)
        usuario = UsuarioPersonalizado.objects.get(username="usuario_con_rol")
        self.assertEqual(usuario.rol.nombre, "auditor")

    # === 3. Creación de usuarios (Admin) ===
    def test_creacion_usuario_por_admin(self):
        self.client.login(username='admin_test', password='admin123')
        response = self.client.post(reverse('usuarios:crear_usuario'), {
            "username": "creado_por_admin",
            "email": "admin_creo@test.com",
            "password1": "Testpass123",
            "password2": "Testpass123",
            "rol": self.rol_viewer.id # ✅ CORRECCIÓN: Campo 'rol' es obligatorio
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(UsuarioPersonalizado.objects.filter(username="creado_por_admin").exists())

    # === 4. Edición de usuarios ===
    def test_editar_usuario(self):
        self.client.login(username="admin_test", password="admin123")
        response = self.client.post(reverse("usuarios:editar_usuario", args=[self.usuario_normal.id]), {
            "username": "user_editado",
            "email": "editado@test.com",
            "es_activo": True,
            "rol": self.rol_auditor.id # ✅ CORRECCIÓN: Campo 'rol' es obligatorio
        })

        if response.status_code == 200:
            print("Errores form editar:", response.context['form'].errors)

        self.assertEqual(response.status_code, 302)
        self.usuario_normal.refresh_from_db()
        self.assertEqual(self.usuario_normal.username, "user_editado")
        self.assertEqual(self.usuario_normal.rol.nombre, "auditor")

    # === 5. Soft delete ===
    def test_desactivar_usuario(self):
        self.client.login(username="admin_test", password="admin123")
        response = self.client.post(reverse("usuarios:accion_usuario", args=[self.usuario_normal.id]),
           {"accion": "desactivar"}                                
        )
        self.assertEqual(response.status_code, 302)
        self.usuario_normal.refresh_from_db()
        self.assertFalse(self.usuario_normal.is_active)
    
    # === 6. Hard delete ===
    def test_eliminar_usuario(self):
        self.client.login(username="root_test", password="root123")
        response = self.client.post(reverse("usuarios:accion_usuario", args=[self.usuario_normal.id]),
           {"accion": "eliminar_fisico"}                                
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(UsuarioPersonalizado.objects.filter(id=self.usuario_normal.id).exists())

    # === EXTRA 2. Redirección al login si no está autenticado ===
    def test_redireccion_si_no_autenticado(self):
        response = self.client.get(reverse("usuarios:lista_usuarios"))
        # Comno no esta autenticado, Django lo redirige al login (302)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("usuarios:login"), response.url)
        
    # === EXTRA 3. Logout ===
    def test_logout(self):
        self.client.login(username="admin_test", password="admin123")
        # Confirmar que accede mientras está logueado
        response = self.client.get(reverse("usuarios:home"))
        self.assertEqual(response.status_code, 200)

        # Logout
        self.client.get(reverse("usuarios:logout"))

        # Intentar acceder de nuevo al home -> Redirige al login
        response = self.client.get(reverse("usuarios:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("usuarios:login"), response.url)

# ============================================================================
# GRUPO A: Tests de Permission Model
# ============================================================================

class PermissionTestCase(TestCase):
    """Tests para el modelo Permission"""

    def test_crear_permission(self):
        """Crear un permiso individual"""
        permission, created = Permission.objects.get_or_create(
            nombre = 'custom_perm_test', # Nombre unico para que no choque con signals
            defaults={'descripcion': 'Test Permiso'}
        )
        self.assertTrue(Permission.objects.filter(nombre='custom_perm_test').exists())

    def test_permission_choices(self):
        """Verificar que los 10 permisos existen (creados por signal)"""
        permisos_esperados = [
            'view_dashboard', 'view_anomalies', 'view_events',
            'create_ticket', 'edit_anomaly', 'download_report',
            'manage_users', 'manage_roles', 'configure_alerts', 'admin_access'
        ]
        # Solo verificar que existen (signals los crean)
        for nombre in permisos_esperados:
            self.assertTrue(
                Permission.objects.filter(nombre=nombre).exists(),
                f"Permiso {nombre} no existe"
            )

# ============================================================================
# GRUPO B: Tests de Role Model
# ============================================================================

class RoleTestCase(TestCase):
    """Tests para el modelo Role"""

    def setUp(self):
        self.permission1, _ = Permission.objects.get_or_create(
            nombre = 'perm_test_1', defaults={'descripcion': 'Test 1'}
        )
    
    def test_crear_role(self):
        # Usamos un nombre nuevo para evitar el signal
        role, _ = Role.objects.get_or_create(
            nombre = 'custom_role', defaults={'descripcion': 'Custom Role'}
        )
        self.assertTrue(Role.objects.filter(nombre='custom_role').exists())

    def test_role_tiene_permiso(self):
        role, _ = Role.objects.get_or_create(
            nombre = 'custom_role_2', defaults={'descripcion': 'Custom 2'}
        )
        role.permisos.add(self.permission1)
        self.assertTrue(role.tiene_permiso('perm_test_1'))

    def test_role_agregar_permiso(self):
        # ✅ CORRECCIÓN: Creamos un rol nuevo y LIMPIO para probar el conteo
        role = Role.objects.create(nombre='role_vacio', descripcion= 'Role Vacio')

        self.assertEqual(role.permisos.count(), 0) # Debe empezar en 0

        role.agregar_permisos('view_dashboard') # Agregamos 1 existente

        self.assertEqual(role.permisos.count(), 1)
        self.assertTrue(role.tiene_permiso('view_dashboard'))

    def test_role_remover_permiso(self):
        role, _ = Role.objects.get_or_create(
            nombre='editor', 
            defaults={'descripcion': 'Editor'}
        )
        role.agregar_permisos('view_dashboard')
        role.remover_permiso('view_dashboard')

        self.assertEqual(role.permisos.count(), 0)

# ============================================================================
# GRUPO C: Tests de UsuarioPersonalizado + Role
# ============================================================================

class UsuarioRoleTestCase(TestCase):
    """Test de asignacion de roles a usuarios"""

    def setUp(self):

        self.rol_admin, _ = Role.objects.get_or_create(
        nombre = 'admin',
        defaults={'descripcion': 'Administrador'}
        )
        self.rol_auditor, _ = Role.objects.get_or_create(
        nombre = 'auditor',
        defaults={'descripcion': 'Auditor'}
        )
        self.rol_viewer, _ = Role.objects.get_or_create(
            nombre = 'viewer',
            defaults={'descripcion': 'Visualizador'}
        )

        # Usar permisos existentes creados por signals
        for i in range(1, 4):
            perm, _ = Permission.objects.get_or_create(
                nombre = f'permiso_{i}',  # ✅ Ahora es {i}
                defaults={'descripcion': f'Permiso {i}'}
            )
            self.rol_admin.permisos.add(perm)

    def test_usuario_asignacion_rol(self):
        usuario = UsuarioPersonalizado.objects.create(
            username='admin_user',
            email ='admin@test.com',
            password = 'testpass123',
            rol = self.rol_admin
        )
        self.assertEqual(usuario.rol.nombre, 'admin')

    def test_usuario_es_admin(self):
        usuario = UsuarioPersonalizado.objects.create_user(
            username='admin_test',
            email= 'admin@test.com',
            password='testpass123',
            rol = self.rol_admin
        )
        self.assertTrue(usuario.es_admin())

    def test_usuario_es_auditor(self):
        usuario = UsuarioPersonalizado.objects.create_user(
            username='auditor_test',
            email='auditor@test.com',
            password='testpass123',
            rol=self.rol_auditor
        )
        self.assertTrue(usuario.es_auditor())

    def test_usuario_es_visualizador(self):
        usuario = UsuarioPersonalizado.objects.create_user(
            username='viewer_test',
            email='viewer@test.com',
            password = 'testpass123',
            rol= self.rol_viewer
        )
        self.assertTrue(usuario.es_visualizador())

    def test_usuario_tiene_permiso(self):
        usuario = UsuarioPersonalizado.objects.create_user(
            username='user_test',
            email='user@test.com',
            password='testpass123',
            rol=self.rol_admin
        )
        self.assertTrue(usuario.tiene_permiso('permiso_1'))

# ============================================================================
# GRUPO D: Tests de Auditoría
# ============================================================================

class AuditoriaTestCase(TestCase):
    """Tests para metodos de auditoria"""

    def setUp(self):
        self.usuario = UsuarioPersonalizado.objects.create_user(
            username='audit_user',
            email='auditor@test.com',
            password='testpass123'
        )

    def test_registrar_acceso(self):
        self.assertIsNone(self.usuario.ultimo_acceso)

        self.usuario.registrar_acceso()
        self.usuario.refresh_from_db()

        self.assertIsNotNone(self.usuario.ultimo_acceso)
        self.assertEqual(self.usuario.intentos_login, 0)

    def test_registrar_intento_fallido(self):
        self.assertEqual(self.usuario.intentos_login, 0)

        self.usuario.registrar_intento_fallido()
        self.usuario.refresh_from_db()

        self.assertEqual(self.usuario.intentos_login, 1)

    def test_bloqueo_tras_5_intentos(self):
        for i in range(5):
            resultado = self.usuario.registrar_intento_fallido()
            if i < 4:
                self.assertTrue(resultado)

        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.es_activo)

    def test_resetear_intentos(self):
        self.usuario.intentos_login =3
        self.usuario.save()

        self.usuario.resetear_intentos_fallido()
        self.usuario.refresh_from_db()

        self.assertEqual(self.usuario.intentos_login, 0)

# ============================================================================
# GRUPO E: Tests de Soft-Delete avanzado
# ============================================================================

class SoftDeleteTestCase(TestCase):
    """Test para soft-delete y restore"""

    def setUp(self):
        self.usuario = UsuarioPersonalizado.objects.create_user(
            username='soft_delete_user',
            email='soft@test.com',
            password='testpass123'
        )

    def test_soft_delete_completo(self):
        self.usuario.soft_delete()
        self.usuario.refresh_from_db()

        self.assertIsNotNone(self.usuario.fecha_eliminacion)
        self.assertFalse(self.usuario.is_active)

    def test_restore_usuario(self):
        self.usuario.soft_delete()
        self.usuario.restore()
        self.usuario.refresh_from_db()

        self.assertIsNone(self.usuario.fecha_eliminacion)
        self.assertTrue(self.usuario.is_active)

    def test_esta_eliminado_property(self):
        self.assertFalse(self.usuario.esta_eliminado)

        self.usuario.soft_delete()
        self.usuario.refresh_from_db()

        self.assertTrue(self.usuario.esta_eliminado)