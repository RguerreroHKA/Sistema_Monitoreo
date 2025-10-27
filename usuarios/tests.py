from django.test import TestCase, Client
from django.contrib.auth.models import Group
from django.urls import reverse
from .models import UsuarioPersonalizado

class ModuloUsuariosTestCase(TestCase):
    def setUp(self):
        # Cliente de prueba
        self.client = Client()

        # Crear grupos
        self.grupo_admin = Group.objects.create(name="Administrador")
        self.grupo_auditor = Group.objects.create(name="Auditor")

        # Crear superusuario
        self.superuser = UsuarioPersonalizado.objects.create_superuser(
            username="root_test", email="root@test.com", password="root123"
        )

        # Crear usuarios, Admin
        self.admin = UsuarioPersonalizado.objects.create_user(
            username="admin_test", email="admin@test.com", password="admin123"
        )
        self.admin.groups.add(self.grupo_admin)

        # Crear usuario, Auditor
        self.auditor = UsuarioPersonalizado.objects.create_user(
            username="auditor_test", email="auditor@test.com", password="auditor123"
        )
        self.auditor.groups.add(self.grupo_auditor)

        # Crear usuario normal (sin grupo)
        self.usuario_normal = UsuarioPersonalizado.objects.create_user(
            username="user_test", email="user@test.com", password="user123"
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

        # Auditor intenta acceder -> Rechazado (403)
        self.client.login(username="auditor_test", password="auditor123")
        #self.client.force_login(self.auditor)
        response = self.client.get(reverse("usuarios:lista_usuarios"))
        self.assertEqual(response.status_code, 403)

        # Usuario sin grupo rechazado
        self.client.login(username="user_test", password= "user123")
        response = self.client.get(reverse("usuarios:lista_usuarios"))
        self.assertEqual(response.status_code,403)

    # === EXTRA 1. Asignación de grupos ===
    def test_asignacion_grupos_en_creacion(self):
        self.client.login(username="admin_test", password="admin123")
        response = self.client.post(reverse("usuarios:crear_usuario"), {
            "username": "usuario_con_grupo",
            "email": "congrupo@test.com",
            "password1": "Testpass123",
            "password2": "Testpass123",
            "groups" : [self.grupo_auditor.id] # Asignar al grupo Auditor
        })
        self.assertEqual(response.status_code, 302)
        usuario = UsuarioPersonalizado.objects.get(username="usuario_con_grupo")
        self.assertTrue(usuario.groups.filter(name="Auditor").exists())

    # === 3. Creación de usuarios (Admin) ===
    def test_creacion_usuario_por_admin(self):
        self.client.login(username='admin_test', password='admin123')
        response = self.client.post(reverse('usuarios:crear_usuario'), {
            "username": "creado_por_admin",
            "email": "admin_creo@test.com",
            "password1": "Testpass123",
            "password2": "Testpass123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(UsuarioPersonalizado.objects.filter(username="creado_por_admin").exists())

    # === 4. Edición de usuarios ===
    def test_editar_usuario(self):
        self.client.login(username="admin_test", password="admin123")
        response = self.client.post(reverse("usuarios:editar_usuario", args=[self.usuario_normal.id]), {
            "username": "user_editado",
            "email": "editado@test.com",
            "is_active": True,
        })
        self.assertEqual(response.status_code, 302)
        self.usuario_normal.refresh_from_db()
        self.assertEqual(self.usuario_normal.username, "user_editado")

    # === 5. Soft delete ===
    def test_desactivar_usuario(self):
        self.client.login(username="admin_test", password="admin123")
        response = self.client.post(reverse("usuarios:accion_usuario", args=[self.usuario_normal.id]),
           {"accion": "desactivar"}                                
        )
        self.assertEqual(response.status_code, 302)
        self.usuario_normal.refresh_from_db()
        self.assertFalse(self.usuario_normal.is_active)#JungKook
    
    # === 6. Hard delete ===
    def test_eliminar_usuario(self):
        self.client.login(username="root_test", password="root123")
        response = self.client.post(reverse("usuarios:accion_usuario", args=[self.usuario_normal.id]),
           {"accion": "eliminar"}                                
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


