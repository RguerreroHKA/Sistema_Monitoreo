from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from .models import UsuarioPersonalizado

class FormularioRegistro(UserCreationForm):
    """ 
        Formulario para el registro de nuevos usuarios. 
        Hereda de UserCreationForm para incluir campos básicos de usuario.
    """
    class Meta:
        model = UsuarioPersonalizado
        fields = ['username', 'email'] # Campos que queremos mostrar en el formulario

class FormularioCrearUsuario(UserCreationForm):
    # Formulario para que un administrador cree nuevos usuarios y los asigne a grupos.
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Asignar Grupos"
    )

    class Meta:
        model = UsuarioPersonalizado
        """
            Importante: password1 y password2 NO van en fields porque 
            son manejados por UserCreationForm.
        """
        fields = ['username', 'email', 'groups']

    def save(self, commit=True):
        """
            Guardamos el usuario con contraseña hasheaada (UserCreationForm lo maneja),
            y luego asignamos los grupos si se han seleccionado.
        """
        usuario = super().save(commit=False) # Creamos instancia del usuario sin guardar aún
        if commit:
            usuario.save() # Se guarda y genera ID
            # Si se selecionaron algunos grupos, los asignamos
            grupos = self.cleaned_data.get('groups')
            if grupos:
                usuario.groups.set(grupos) # Relacion (BD) de muchos a muchos (ManyToMany)
        return usuario