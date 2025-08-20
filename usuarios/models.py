from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class UsuarioPersonalizado(AbstractUser):
    """
    Modelo de usuario personalizado que extiende AbstractUser
    Se pueden agregar campos adicionales si es necesario a futuro
    """
    pass

    def __str__(self):
        return self.username