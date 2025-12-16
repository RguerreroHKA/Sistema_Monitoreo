from django.test import TestCase, Client
from usuarios.models import UsuarioPersonalizado
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import EventoDeAcceso
import json

class EventoDeAccesoModelTests(TestCase):
    """
        Tests para el modelo EventoDeAcceso (Sprint 2)
    """

    def setUp(self):
        """Preparar datos de prueba"""
        self.evento = EventoDeAcceso.objects.create(
            id_evento_google = 'unique_id_123',
            email_usuario = 'test@example.com',
            direccion_ip = '192.168.1.1',
            timestamp = timezone.now(),
            archivo_id = 'file123',
            nombre_archivo = 'documento.pdf',
            tipo_evento = 'view',
            es_anomalia=False,
            detalles={'source': 'test'}
        )
    
    def test_crear_evento(self):
        """Verificar que se crea un evento correctamente"""
        self.assertTrue(EventoDeAcceso.objects.filter(id=self.evento.id).exists())
        self.assertEqual(self.evento.email_usuario, 'test@example.com')
        # Verificamos que se guardo el ID de google
        self.assertEqual(self.evento.id_evento_google, 'unique_id_123')
    
    def test_evento_por_defecto_no_es_anomalia(self):
        """Verificar que los eventos nuevos no son anomalias por defecto"""
        evento = EventoDeAcceso.objects.create(
            id_evento_google = 'unique_id_456',
            email_usuario='otro@example.com',
            direccion_ip='10.0.0.1',
            timestamp=timezone.now(),
            archivo_id = 'file456',
            nombre_archivo = 'imagen.jpg',
            tipo_evento = 'download'
        )
        self.assertFalse(evento.es_anomalia)
    
    def test_str_representation(self):
        """Verificar la representacion en string del evento"""
        str_evento = str(self.evento)
        # Ajustamos esto porque el __str__ ahora tiene formato fecha
        self.assertIn('test@example.com', str_evento)
        self.assertIn('view', str_evento)

    def test_evento_anomalia(self):
        """Verificar que se puede marcar un evento como anomalia"""
        # Debemos asignar un score para que la signal de alerta no falle
        self.evento.es_anomalia = True
        self.evento.anomaly_score = 0.95
        self.evento.severidad = 'ALTA'
        self.evento.save()

        evento_actualizado = EventoDeAcceso.objects.get(id=self.evento.id)
        self.assertTrue(evento_actualizado.es_anomalia)

class AdminInterfaceTests(TestCase):
    """
        Tests para la interfaz de administracion (sprint 2)
    """

    def setUp(self):
        """Preparar admin y cliente"""
        self.client = Client()
        self.admin = UsuarioPersonalizado.objects.create_superuser(
            username='admin_test',
            email='admin@example.com',
            password='adminpass123'
        )

        EventoDeAcceso.objects.create(
            id_evento_google= 'admin_test_event',
            email_usuario='user@example.com',
            direccion_ip='192.168.1.1',
            timestamp = timezone.now(),
            archivo_id = 'file1',
            nombre_archivo = 'test.pdf',
            tipo_evento='view',
            es_anomalia=False
        )
    
    def test_admin_login(self):
        """Verificar que el admin puede ingresar"""
        response = self.client.post(reverse('admin:login'), {
            'username': 'admin_test',
            'password': 'adminpass123'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_admin_eventos_listado(self):
        """Verificar que el listado de eventos en admin funciona"""
        self.client.login(username='admin_test', password='adminpass123')
        # Django admin URLs: admin:app_model_changelist
        response = self.client.get(reverse('admin:monitoreo_eventodeacceso_changelist'))

        self.assertEqual(response.status_code, 200)
        # Verificamos que el email aparezca en el HTML de respuesta
        self.assertContains(response, 'user@example.com')