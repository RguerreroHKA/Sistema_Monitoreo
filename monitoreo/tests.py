from django.test import TestCase, Client
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from usuarios.models import UsuarioPersonalizado
from .models import EventoDeAcceso
# Importamos las funciones de alerta del Sprint 6
from .utils_alertas import debe_enviar_alerta, enviar_alerta_anomalia, puede_enviar_alerta
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

class SistemaAlertaTests(TestCase):
    """
        Tests para el Sistema de Alertas y Notificaciones (SPRINT 6)
        Verifica: Filtros de severidad, Anti-Spam (Caché) y Contenido de Email.
    """

    def setUp(self):
        """Configuración inicial antes de cada prueba"""
        # Limpiar caché para evitar interferencias entre tests
        cache.clear()

        # Crear un evento base simulado una anomalía detectada
        self.evento = EventoDeAcceso.objects.create(
            id_evento_google='TEST-ALERT-001',
            email_usuario="hacker@test.com",
            tipo_evento="delete",
            timestamp=timezone.now(),
            direccion_ip="192.168.66.6",
            nombre_archivo="datos_sensibles.pdf",
            es_anomalia=True,
            severidad='MEDIA', # Empezamos con MEDIA para probar el filtro
            anomaly_score=0.55,
            motivo_anomalia="Acceso en horario inusual (3:00 AM)"
        )

    def test_filtro_severidad_ignora_baja_media(self):
        """Prueba que NO se envíe alerta si la severidad es BAJA o MEDIA"""
        # Caso Media
        self.evento.severidad = 'MEDIA'
        self.assertFalse(debe_enviar_alerta(self.evento), "No debería alertar severidad MEDIA")

        # Caso Baja
        self.evento.severidad = 'BAJA'
        self.assertFalse(debe_enviar_alerta(self.evento), "No debería alertar severidad BAJA")
    
    def test_filtro_severidad_permite_alta_critica(self):
        """Prueba que SÍ se envíe alerta si es ALTA o CRITICA"""
        # Caso Alta
        self.evento.severidad = 'ALTA'
        self.assertTrue(debe_enviar_alerta(self.evento), "Debería alertar severidad ALTA")

        cache.clear()

        # Caso Crítica
        self.evento.severidad = 'CRITICA'
        self.assertTrue(debe_enviar_alerta(self.evento), "Debería permitir alerta CRITICA")

    def test_cache_antispam_bloquea_duplicados(self):
        """
            Prueba que el sistema bloquee alertas repetidas del mismo evento 
            dentro de la ventana de tiempo (5 minutos).
        """

        # 1. Primera vez: Debe dejar pasar (retorna True
        self.assertTrue(puede_enviar_alerta(self.evento.id, ventana_minutos=5))

        # 2. Segunda vez inmediata: Debe bloquear (retorna False) porque está en caché
        self.assertFalse(puede_enviar_alerta(self.evento.id, ventana_minutos=5))

        # 3. Limpiamos caché (simulando que pasaron más de 5 minutos)
        cache.clear()
        # Ahora debería dejar pasar de nuevo
        self.assertTrue(puede_enviar_alerta(self.evento.id, ventana_minutos=5))

    def test_contenido_correo_alerta(self):
        """
            Prueba que el correo se construya con el asunto correcto 
            y contenga el MOTIVO de la anomalía en el cuerpo.
        """
        self.evento.severidad = 'CRITICA'
        
        # Ejecutamos el envio real (simulado en memoria por Django)
        enviar_alerta_anomalia(self.evento)

        # Verificamos buzón de salida
        self.assertEqual(len(mail.outbox), 1, "Debería haber 1 correo en bandeja de salida")

        email = mail.outbox[0]

        # Verificación de contenido
        self.assertIn("ANOMALÍA CRITICA", email.subject) # Asunto correcto
        self.assertIn("datos_sensibles.pdf", email.subject) # Archivo en asunto
        self.assertIn("Acceso en horario inusual", email.body) # Motivo en el cuerpo
        self.assertIn("hacker@test.com", email.body) # Usuario en el cuerpo