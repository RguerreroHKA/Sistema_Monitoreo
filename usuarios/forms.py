from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import UsuarioPersonalizado, Role

class FormularioRegistro(UserCreationForm):
    """ 
        Formulario para el autoregistro de nuevos usuarios. 
        Por defecto, un usuario registrado por aquí no tiene Rol (o se le asigna Viewer en la vista).
    """
    
    def clean_email(self):
        """Validar que el email no esté registrado."""
        email = self.cleaned_data.get('email')

        # Verifica si ya existe el email
        if UsuarioPersonalizado.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "Este email ya está registrado. ¿Olvidaste tu contraseña? "
                "Recuperala en /usuarios/reinicio-clave/"
            )
        return email
    
    class Meta:
        model = UsuarioPersonalizado
        fields = ['username', 'email'] # Campos que queremos mostrar en el formulario

        

class FormularioCrearUsuario(UserCreationForm):
    """Formulario para que un administrador cree nuevos usuarios y les asigne un ROL."""
    # Se Teemplaza 'groups' por 'rol'
    rol = forms.ModelChoiceField(
        queryset= Role.objects.filter(activo=True), #Solo roles activos
        required= True, #Obligado asignar un rol al crear
        widget= forms.Select(attrs={'class': 'form-control'}),
        label="Asignar Rol",
        empty_label= "Seleccione un Rol"
    )

    class Meta:
        model = UsuarioPersonalizado
        """
            Importante: password1 y password2 NO van en fields porque 
            son manejados por UserCreationForm.
        """
        fields = ['username', 'email', 'rol']

    # Nota: Se deja de usar el metodo def save(). ya que no hace falta sobreescribir,
    # Al ser 'rol' una FK en el modelo, Django lo guarda automaticamente
    
class FormularioEditarUsuario(UserChangeForm):
    """
        Formulario para que los administradoes puedan editar usuarios existentes.
        Permite cambiar el ROL y el estado de activación.
        Hereda de UserChangeForm para incluir campos básicos de usuario y no reinventar la rueda.
    """
    password = None # Ocultamos el campo password

    rol = forms.ModelChoiceField(
        queryset=Role.objects.filter(activo=True),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Rol Asignado"
    )

    class Meta:
        model = UsuarioPersonalizado
        # Usamos 'es_activo' (el campo personalizado) o 'is_active' (django nativo).
        # Como los sincronizamos en el modelo, usaremos 'es_activo' para ser consistentes.
        fields = ['username', 'email', 'rol', 'es_activo']
        # is_active permite activar/desactivar usuarios sin borrarlos
        # groups permite asignar o cambiar grupos del usuario
    
    widgets = {
        'username':  forms.TextInput(attrs={'class': 'form-control'}),
        'email':     forms.EmailInput(attrs={'class': 'form-control'}),
        'es_activo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
    }
