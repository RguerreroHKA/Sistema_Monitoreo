from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetConfirmView, PasswordResetCompleteView, PasswordResetDoneView
    )
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy
from .forms import FormularioRegistro, FormularioCrearUsuario, FormularioEditarUsuario
from .models import UsuarioPersonalizado

# ============================================================================
# DECORADORES Y FUNCIONES DE ACCESO (Alineados con models.py)
# ============================================================================

# Decorador: Solo Admins - UTILIZA EL MÉTODO DEL MODELO
def es_administrador(usuario):
    """Verifica si el usuario es un Administrador (basado en el campo 'rol')."""
    # Si el usuario es un superusuario (para mantenimiento) o tiene el rol 'admin'
    return usuario.is_authenticated and (usuario.is_superuser or (hasattr(usuario, 'rol') and usuario.es_admin()))

# Decorador: Solo Auditores y Admins
def es_auditor_o_admin(usuario):
    """Verifica si el usuario es Auditor o Administrador."""
    if not usuario.is_authenticated:
        return False
    # Usamos los metodos de nuestro modelo UsuarioPersonalizado
    return usuario.is_superuser or (hasattr(usuario, 'rol') and (usuario.es_admin() or usuario.es_audito()))

# Decorador: Permiso General (Recomendado para la logica de la tesis)
def tiene_permiso(nombre_permiso):
    """Factory para crear un decorador que verifica un permiso especifico"""
    def check_permission(usuario):
        if not usuario.is_authenticated:
            return False
        # Superusuario siempre tiene acceso
        if usuario.is_superuser:
            return True
        # Usa el metodo tiene_permiso() del modeloo
        return hasattr(usuario, 'rol') and usuario.tiene_permiso(nombre_permiso)
    return user_passes_test(check_permission, login_url='/usuarios/login/')

# ============================================================================
# VISTAS PROTEGIDAS (Gestión de Usuarios)
# ============================================================================

#Prueba de vista para grupo Administrador
@user_passes_test(es_administrador)
def vista_admin_only(request):
    return render(request, 'usuarios/admin_only.html')

# Aplicando el nuevo decorador de permisos (requiere manage_users)
@tiene_permiso('manage_users')
def lista_usuarios(request):
    """
        Vista para listar todos los usuarios (solo quienes tengan permiso 'manage_users').
    """
    # Nota: Nota: El decorador maneja la restricción de acceso, no necesitamos el 'if not es_administrador...' interno.
    
    # Prefetch del rol para evitar consultas N+1
    usuarios = UsuarioPersonalizado.objects.all().select_related('rol').order_by('-fecha_creacion')
    
    # Paginación: 10 usuarios por página
    paginator = Paginator(usuarios, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    
    return render(request, 'usuarios/lista_usuarios.html', context)

@tiene_permiso('manage_users')
def crear_usuario(request):
    # Nota: El decorador usesr_passes_test se ocua de que solo usuarios con 'manage_users' lleguen aquí.
    if request.method == 'POST':
        form = FormularioCrearUsuario(request.POST)
        if form.is_valid():
            #1. Guardamos el objeto pero NO lo enviamos a la BD todavia (commit=False)
            usuario = form.save(commit=False)

            #2. Verificamos si se selecciono un rol. Si no, asignamos 'viewer'
            if not usuario.rol:
                from .models import Role # Importacion local para evitar ciclos
                try:
                    rol_viewer = Role.objects.get(nombre='viewer')
                    usuario.rol = rol_viewer
                except Role.DoesNotExist:
                    pass # Si no existe el rol, se guardara como None (o manehar error)

            #3. Ahora si guardamos definitivamente en la BD
            usuario.save()

            messages.success(request, f"Usuario {usuario.username} creado exitosamente.")
            return redirect('usuarios:lista_usuarios')
    else:
        form = FormularioCrearUsuario()
    return render(request, 'usuarios/crear_usuario.html', {'form': form})

@tiene_permiso('manage_users')
def editar_usuario(request, usuario_id):
    """
        Permite a un administrador editar la información de un usuario existente.    
    """
    usuario = get_object_or_404(UsuarioPersonalizado, id=usuario_id)

    if request.method == 'POST':
        form = FormularioEditarUsuario(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, f"Usuario {usuario.username} editado exitosamente.")
            return redirect('usuarios:lista_usuarios')
    else:
        form = FormularioEditarUsuario(instance=usuario)
        
    return render(request, "usuarios/editar_usuario.html", {"form": form, "usuario": usuario})
    
@tiene_permiso('manage_users')
def accion_usuario(request, usuario_id):
    """
        Permite a un administrador desactivar, restaurar o (si es superusuario) eliminar un usuario.
        Aquí implementamos el soft_delete que es requerido por ISO 27001 para auditoría.
    """
    usuario = get_object_or_404(UsuarioPersonalizado, id=usuario_id)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'desactivar':
            # Implementamos soft_delete, que desactiva is_active/es_activo y registra la fecha.
            usuario.soft_delete()
            messages.warning(request, f"Usuario {usuario.username} desactivado (soft-delete) por seguridad.")

        elif accion == 'activar':
            # Implementamos restore, que revierte el soft-delete
            usuario.restore()
            messages.success(request, f"Usuario {usuario.username} restaurado y activado.")

        elif accion == 'eliminar_fisico' and request.user.is_superuser:
            # Opcion solo para superusuario, NO se recomienda para datos auditables.
            usuario.delete()
            messages.error(request, f"Usuario {usuario.username} eliminado PERMANENTEMENTE.")
        
        return redirect('usuarios:lista_usuarios')
    
    return render(request, 'usuarios/accion_usuario.html', {
        'usuario': usuario,
        'es_superuser': request.user.is_superuser,
        'es_admin_sistema': request.user.es_admin() # Variable para uso en templates
    })
    
# ============================================================================
# VISTAS DE AUTENTICACIÓN Y AUDITORÍA
# ============================================================================



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
    """
        Vista de login que implementa el registro de acceso (Auditoría ISO 27001) 
        y la lógica de bloqueo de cuenta por intentos fallidos.
    """
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        # Primero, buscamos el usuario sin autenticar para manejar intentos fallidos.
        try:
            usuario_obj = UsuarioPersonalizado.objects.get(username=username)
        except UsuarioPersonalizado.DoesNotExist:
            # No encontramos el usuario, error genérico para no dar pistas
            return render(request, 'usuarios/login.html', {'error': 'Credenciales inválidas'})
        
        # 1. Verificar si el usuario esta bloqueado o desactivado
        if not usuario_obj.es_activo:
            # Retrona un error especifico si esta desaactivado por un administrador o bloqueo
            messages.error(request, "Su cuenta se encuentra inactiva o ha sido bloqueada. Contacte al administrador")
            return render(request, 'usuarios/login.html')
        
        # 2. Intentar autenticar el usuario
        usuario = authenticate(request, username=username, password=password)

        if usuario is not None:
            #A. Login Exitoso
            login(request, usuario)
            usuario.registrar_acceso() # Auditoria de ISO 27001
            messages.success(request, f"Bienvenido, {usuario.username}. Acceso registrado")
            return redirect('usuarios:home')
        
        else:
            # B. CREDENCUALES INVALIDAS
            # Se registra un intento falldio y se verifica si la cuenta debe bloquearse.
            puede_intentar = usuario_obj.registrar_intento_fallido()

            if not puede_intentar:
                messages.error(request, "Demasiados intentos fallidos. Su cuenta ha sido BLOQUEADA automaticamente.")
            else:
                messages.error(request, 'Credenciales inválidas. Intento fallido #{}'.format(usuario_obj.intentos_login))
            
            return render(request, 'usuarios/login.html')
        
    return render(request, 'usuarios/login.html')

@login_required
def home_view(request):
    # Uso del metodo del modelo para la logica centralizada
    es_admin = request.user.es_admin()

    # Ejemplo de uso de permisos para el template
    puede_ver_anomalias = request.user.puede_ver_anomalias()

    context = {
        'es_admin': es_admin,
        'puede_ver_anomalias': puede_ver_anomalias
    }

    return render(request, 'usuarios/home.html', context)

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