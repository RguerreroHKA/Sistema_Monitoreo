from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import UsuarioPersonalizado

class FormularioRegistro(UserCreationForm):
    """ Formulario para el registro de nuevos usuarios. 
        Hereda de UserCreationForm para incluir campos básicos de usuario.
    """
    class Meta:
        model = UsuarioPersonalizado
        fields = ['username', 'email'] # Campos que queremos mostrar en el formulario