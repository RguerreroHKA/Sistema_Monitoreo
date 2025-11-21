from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, PasswordResetCompleteView, PasswordResetDoneView
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy
from .forms import FormularioRegistro, FormularioCrearUsuario, FormularioEditarUsuario
from .models import UsuarioPersonalizado

# Decorador: Solo Admins
def es_administrador(usuario):
    return usuario.is_authenticated and (usuario.is_superuser or usuario.groups.filter(name='Administrador').exists())
"""
    Si se quiere solo admins (sin superuser) usar:
    return usuario.is_authenticated and usuario.groups.filter(name='Administrador').exists()
"""

#Prueba de vista para grupo Administrador
@user_passes_test(es_administrador)
def vista_admin_only(request):
    return render(request, 'usuarios/admin_only.html')

#@user_passes_test(es_administrador)
@login_required
def lista_usuarios(request):
    """
    Vista para listar todos los usuarios (solo admin).
    Incluye paginación de 10 usuarios por página.
    """
    if not es_administrador(request.user):
        return HttpResponseForbidden("No tienes permiso para ver esta página.")
    
    # Prefetch de grupos para evitar consultas N+1
    usuarios = UsuarioPersonalizado.objects.all().prefetch_related('groups').order_by('-fecha_creacion')
    
    # Paginación: 10 usuarios por página
    paginator = Paginator(usuarios, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'usuarios': page_obj.object_list,  # Para compatibilidad con template
    }
    
    return render(request, 'usuarios/lista_usuarios.html', context)

@login_required
@user_passes_test(es_administrador)
def crear_usuario(request):
    if request.method == 'POST':
        form = FormularioCrearUsuario(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario creado exitosamente.")
            return redirect('usuarios:lista_usuarios')
    else:
        form = FormularioCrearUsuario()
    return render(request, 'usuarios/crear_usuario.html', {'form': form})

@login_required
@user_passes_test(es_administrador)
def editar_usuario(request, usuario_id):
    """
        Permite a un administrador editar la información de un usuario existente.    
    """
    usuario = get_object_or_404(UsuarioPersonalizado, id=usuario_id)

    if request.method == 'POST':
        form = FormularioEditarUsuario(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            return redirect('usuarios:lista_usuarios')
    else:
        form = FormularioEditarUsuario(instance=usuario)
        
    return render(request, "usuarios/editar_usuario.html", {"form": form, "usuario": usuario})
    
@login_required
@user_passes_test(es_administrador)
def accion_usuario(request, usuario_id):
    """
        Permite a un administrador desactivar un usuario existente, si es superusuario se puede eliminar.
    """
    usuario = get_object_or_404(UsuarioPersonalizado, id=usuario_id)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'desactivar':
            usuario.is_active = False
            usuario.save()
        elif accion == 'eliminar' and request.user.is_superuser:
            usuario.delete()
        
        return redirect('usuarios:lista_usuarios')
    
    return render(request, 'usuarios/accion_usuario.html', {'usuario': usuario, 'es_superuser': request.user.is_superuser})
    
    # confirmación antes de eliminar


def registro_view(request):
    if request.method == 'POST':
        form = FormularioRegistro(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            return redirect('usuarios:home')
    else:
        form = FormularioRegistro()
    return render(request, 'usuarios/registro.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        usuario = authenticate(request, username=username, password=password)
        if usuario is not None:
            login(request, usuario)
            return redirect('usuarios:home')
        else:
            return render(request, 'usuarios/login.html', {'error': 'Credenciales invalidas'})
    return render(request, 'usuarios/login.html')

@login_required
def home_view(request):
    es_admin = request.user.groups.filter(name='Administrador').exists()
    return render(request, 'usuarios/home.html', {'es_admin': es_admin})

def logout_view(request):
    logout(request)
    return redirect('usuarios:login')

class ReinicioClave(PasswordResetView):
    template_name = 'usuarios/reinicio_clave.html' # password_reset.html
    email_template_name = 'usuarios/email_reinicio_clave.html' # password_reset_email.html
    success_url = reverse_lazy('usuarios:reinicio_clave_confirmacion') # password_reset_done
    from_email = 'noreply@thefactoryhka.com'

class ReinicioClaveConfimacion(PasswordResetDoneView):
    template_name = 'usuarios/reinicio_clave_confirmacion.html' # password_reset_done

class ReinicioClaveConfimar(PasswordResetConfirmView):
    template_name = 'usuarios/reinicio_clave_confirmar.html' # password_reset_confirm.html
    success_url = reverse_lazy('usuarios:reinicio_clave_exitoso') # password_reset_complete.html

class ReinicioClaveExitoso(PasswordResetCompleteView):
    template_name = 'usuarios/reinicio_clave_exitoso.html' # password_reset_complete.html