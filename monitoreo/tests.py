from django.test import TestCase, Client
from usuarios.models import UsuarioPersonalizado
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import EventoDeAcceso
import json

class EventoDeAccesoModelTests(TestCase):
    """
    Tests para el modelo EventoDeAcceso
    
    Verifica:
    - Creación de eventos
    - Validación de campos
    - Métodos personalizados
    """

    def setUp(self):
        """Preparar datos de prueba"""
        self.evento = EventoDeAcceso.objects.create(
            email_usuario='test@example.com',
            direccion_ip='192.168.1.1',
            timestamp=timezone.now(),
            archivo_id='file123',
            nombre_archivo='documento.pdf',
            tipo_evento='view',
            es_anomalia=False,
            detalles={'source': 'test'}
        )

    def test_crear_evento(self):
        """Verificar que se crea un evento correctamente"""
        self.assertTrue(EventoDeAcceso.objects.filter(id=self.evento.id).exists())
        self.assertEqual(self.evento.email_usuario, 'test@example.com')

    def test_evento_por_defecto_no_es_anomalia(self):
        """Verificar que los eventos nuevos no son anomalías por defecto"""
        evento = EventoDeAcceso.objects.create(
        email_usuario='otro@example.com',
        direccion_ip='10.0.0.1',
        timestamp=timezone.now(),
        archivo_id='file456',
        nombre_archivo='imagen.jpg',
        tipo_evento='download'
        )
        self.assertFalse(evento.es_anomalia)

    def test_str_representation(self):
        """Verificar la representación en string del evento"""
        str_evento = str(self.evento)
        self.assertIn('test@example.com', str_evento)
        self.assertIn('documento.pdf', str_evento)

    def test_evento_anomalia(self):
        """Verificar que se puede marcar un evento como anomalía"""
        self.evento.es_anomalia = True
        self.evento.save()
        evento_actualizado = EventoDeAcceso.objects.get(id=self.evento.id)
        self.assertTrue(evento_actualizado.es_anomalia)

class DashboardAnomaliastests(TestCase):
    """
    Tests para la vista dashboard_anomalias (legacy)
    
    Verifica:
    - Acceso sin login
    - Carga del template
    - Contexto con anomalías
    """

    def setUp(self):
        """Preparar cliente de prueba"""
        self.client = Client()
        self.user = UsuarioPersonalizado.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_dashboard_anomalias_sin_login(self):
        """Verificar que redirige si no está autenticado"""
        response = self.client.get(reverse('monitoreo:dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect

    def test_dashboard_anomalias_con_login(self):
        """Verificar que carga si está autenticado"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('monitoreo:dashboard-v2'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_anomalias_template(self):
        """Verificar que usa el template correcto"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('monitoreo:dashboard-v2'))
        self.assertTemplateUsed(response, 'monitoreo/dashboard.html')
    
    def test_dashboard_contexto_anomalias(self):
        """Verificar que el contexto incluye anomalías"""
        # Crear anomalías
        EventoDeAcceso.objects.create(
            email_usuario='admin@example.com',
            direccion_ip='192.168.1.1',
            timestamp=timezone.now(),
            archivo_id='file1',
            nombre_archivo='confidencial.pdf',
            tipo_evento='view',
            es_anomalia=True
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('monitoreo:dashboard-v2'))
        
        self.assertIn('total_anomalias', response.context)
        self.assertEqual(response.context['total_anomalias'], 1)

class DashboardMonitoreoTests(TestCase):
    """
    Tests para la vista dashboard_monitoreo (nueva)
    
    Verifica:
    - Carga con datos
    - Filtros funcionan
    - Paginación funciona
    """

    def setUp(self):
        """Preparar datos y cliente"""
        self.client = Client()
        self.user = UsuarioPersonalizado.objects.create_user(
            username='monitor',
            password='pass123'
        )
        
        # Crear eventos de prueba
        for i in range(55):
            EventoDeAcceso.objects.create(
                email_usuario=f'user{i}@example.com',
                direccion_ip='192.168.1.1',
                timestamp=timezone.now() - timedelta(days=i),
                archivo_id=f'file{i}',
                nombre_archivo=f'archivo_{i}.pdf',
                tipo_evento='view' if i % 3 == 0 else 'download',
                es_anomalia=i % 10 == 0  # Cada 10 es anomalía
            )
    
    def test_dashboard_monitoreo_carga(self):
        """Verificar que el dashboard carga"""
        self.client.login(username='monitor', password='pass123')
        response = self.client.get(reverse('monitoreo:dashboard-v2'))
        self.assertEqual(response.status_code, 200)
    
    def test_dashboard_monitoreo_estadisticas(self):
        """Verificar que muestra estadísticas"""
        self.client.login(username='monitor', password='pass123')
        response = self.client.get(reverse('monitoreo:dashboard-v2'))
        
        self.assertIn('total_eventos', response.context)
        self.assertIn('total_anomalias', response.context)
        self.assertEqual(response.context['total_eventos'], 55)
        self.assertEqual(response.context['total_anomalias'], 6)
    
    def test_dashboard_monitoreo_paginacion(self):
        """Verificar que la paginación funciona"""
        self.client.login(username='monitor', password='pass123')
        response = self.client.get(reverse('monitoreo:dashboard-v2') + '?page=1')
        
        self.assertIn('page_obj', response.context)
        self.assertEqual(response.context['page_obj'].number, 1)
    
    def test_dashboard_monitoreo_filtro_anomalia(self):
        """Verificar que el filtro de anomalías funciona"""
        self.client.login(username='monitor', password='pass123')
        response = self.client.get(reverse('monitoreo:dashboard-v2') + '?anomalia=si')
        
        self.assertEqual(response.context['filtro_anomalia'], 'si')
    
    def test_dashboard_monitoreo_filtro_usuario(self):
        """Verificar que el filtro de usuario funciona"""
        self.client.login(username='monitor', password='pass123')
        response = self.client.get(reverse('monitoreo:dashboard-v2') + '?usuario=user1')
        
        self.assertEqual(response.context['filtro_usuario'], 'user1')

class APISincronizarTests(TestCase):
    """
    Tests para API de sincronización
    
    Verifica:
    - Método POST requerido
    - Autenticación requerida
    - Respuesta JSON correcta
    """

    def setUp(self):
        """Preparar cliente"""
        self.client = Client()
        self.user = UsuarioPersonalizado.objects.create_user(
            username='apiuser',
            password='apipass123'
        )
    
    def test_api_sincronizar_sin_login(self):
        """Verificar que redirige sin autenticación"""
        response = self.client.post(reverse('monitoreo:api_sincronizar'))
        self.assertEqual(response.status_code, 302)  # Redirect
    
    def test_api_sincronizar_get_no_permitido(self):
        """Verificar que GET no está permitido"""
        self.client.login(username='apiuser', password='apipass123')
        response = self.client.get(reverse('monitoreo:api_sincronizar'))
        self.assertEqual(response.status_code, 405)  # Method Not Allowed
    
    def test_api_sincronizar_post(self):
        """Verificar que POST funciona"""
        self.client.login(username='apiuser', password='apipass123')
        response = self.client.post(reverse('monitoreo:api_sincronizar'))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('success', data)
    
    def test_api_sincronizar_respuesta_json(self):
        """Verificar que la respuesta es JSON válido"""
        self.client.login(username='apiuser', password='apipass123')
        response = self.client.post(reverse('monitoreo:api_sincronizar'))
        
        try:
            data = response.json()
            self.assertIsInstance(data, dict)
            self.assertIn('success', data)
            self.assertIn('mensaje', data)
        except json.JSONDecodeError:
            self.fail("Response no es JSON válido")
    
class APIDeteccionTests(TestCase):
    """
    Tests para API de detección de anomalías
    
    Verifica:
    - Método POST requerido
    - Autenticación requerida
    - Marca eventos como anomalías
    """

    def setUp(self):
        """Preparar cliente y eventos"""
        self.client = Client()
        self.user = UsuarioPersonalizado.objects.create_user(
            username='detectuser',
            password='detectpass123'
        )
        
        # Crear algunos eventos normales
        for i in range(5):
            EventoDeAcceso.objects.create(
                email_usuario=f'user{i}@example.com',
                direccion_ip='192.168.1.1',
                timestamp=timezone.now(),
                archivo_id=f'file{i}',
                nombre_archivo=f'archivo{i}.txt',
                tipo_evento='view',
                es_anomalia=False
            )
    
    def test_api_detectar_sin_login(self):
        """Verificar que redirige sin autenticación"""
        response = self.client.post(reverse('monitoreo:api_detectar'))
        self.assertEqual(response.status_code, 302)
    
    def test_api_detectar_post(self):
        """Verificar que POST funciona"""
        self.client.login(username='detectuser', password='detectpass123')
        response = self.client.post(reverse('monitoreo:api_detectar'))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('success', data)
    
    def test_api_detectar_respuesta_campos(self):
        """Verificar que la respuesta incluye campos necesarios"""
        self.client.login(username='detectuser', password='detectpass123')
        response = self.client.post(reverse('monitoreo:api_detectar'))
        
        data = response.json()
        self.assertIn('anomalias_detectadas', data)
        self.assertIn('eventos_procesados', data)
        self.assertIn('mensaje', data)


class AdminInterfaceTests(TestCase):
    """
    Tests para la interfaz de administración
    
    Verifica:
    - Admin registrado
    - Listado funciona
    - Filtros disponibles
    """

    def setUp(self):
        """Preparar admin y cliente"""
        self.client = Client()
        self.admin = UsuarioPersonalizado.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        EventoDeAcceso.objects.create(
            email_usuario='user@example.com',
            direccion_ip='192.168.1.1',
            timestamp=timezone.now(),
            archivo_id='file1',
            nombre_archivo='test.pdf',
            tipo_evento='view',
            es_anomalia=False
        )

    def test_admin_login(self):
        """Verificar que el admin puede ingresar"""
        response = self.client.post(reverse('admin:login'), {
            'username': 'admin',
            'password': 'adminpass123'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
    
    def test_admin_eventos_listado(self):
        """Verificar que el listado de eventos en admin funciona"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('admin:monitoreo_eventodeacceso_changelist'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'user@example.com')
    
    def test_admin_evento_detalle(self):
        """Verificar que se puede ver el detalle de un evento"""
        evento = EventoDeAcceso.objects.first()
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(
            reverse('admin:monitoreo_eventodeacceso_change', args=[evento.id])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'user@example.com')

class IntegracionTests(TestCase):
    """
    Tests de integración completa
    
    Verifica:
    - Flujo completo: sincronizar → detectar → notificar
    - Datos consistentes
    """

    def setUp(self):
        """Preparar cliente y usuario"""
        self.client = Client()
        self.user = UsuarioPersonalizado.objects.create_user(
            username='integtest',
            password='pass123'
        )
    
    def test_flujo_completo(self):
        """Verificar flujo completo"""
        self.client.login(username='integtest', password='pass123')
        
        # 1. Verificar que el dashboard carga sin eventos
        response = self.client.get(reverse('monitoreo:dashboard'))
        self.assertEqual(response.context['total_eventos'], 0)
        
        # 2. Crear un evento manualmente
        EventoDeAcceso.objects.create(
            email_usuario='test@example.com',
            direccion_ip='192.168.1.1',
            timestamp=timezone.now(),
            archivo_id='file1',
            nombre_archivo='documento.pdf',
            tipo_evento='view'
        )
        
        # 3. Verificar que aparece en el dashboard
        response = self.client.get(reverse('monitoreo:dashboard'))
        self.assertEqual(response.context['total_eventos'], 1)
        self.assertEqual(response.context['total_anomalias'], 0)
    
    def test_consistencia_datos(self):
        """Verificar que los datos son consistentes"""
        # Crear eventos
        for i in range(10):
            EventoDeAcceso.objects.create(
                email_usuario=f'user{i}@example.com',
                direccion_ip='192.168.1.1',
                timestamp=timezone.now(),
                archivo_id=f'file{i}',
                nombre_archivo=f'file{i}.pdf',
                tipo_evento='view',
                es_anomalia=i % 2 == 0
            )
        
        # Verificar totales
        total = EventoDeAcceso.objects.count()
        anomalias = EventoDeAcceso.objects.filter(es_anomalia=True).count()
        
        self.assertEqual(total, 10)
        self.assertEqual(anomalias, 5)