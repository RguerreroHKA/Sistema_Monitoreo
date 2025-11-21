from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


# Create your models here.
class UsuarioPersonalizado(AbstractUser):
    """
    Modelo de usuario personalizado que extiende AbstractUser.
    Incluye campos para soft-delete con timestamps para marcas de tiempo.
    """
    
    # Timestamps
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
    
    def __str__(self):
        return self.username
    
    def soft_delete(self):
        """Marca el usuario como eliminado sin borrar del DB (soft-delete)"""
        self.fecha_eliminacion = timezone.now()
        self.is_active = False
        self.save()
    
    def restore(self):
        """Restaura un usuario eliminado (soft-delete reverso)"""
        self.fecha_eliminacion = None
        self.is_active = True
        self.save()
    
    @property
    def esta_eliminado(self):
        """Retorna True si el usuario fue eliminado"""
        return self.fecha_eliminacion is not None
    
    class Meta:
        verbose_name = "Usuario Personalizado"
        verbose_name_plural = "Usuarios Personalizados"
