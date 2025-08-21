from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import FormularioRegistro
from .models import UsuarioPersonalizado

# Create your views here.

def es_administrador(usuario):
    return usuario.is_authenticated and usuario.groups.filter(name='Administrador').exists()

#Prueba de vista para grupo Administrador
@user_passes_test(es_administrador)
def vista_admin_only(request):
    return render(request, 'usuarios/admin_only.html')

@user_passes_test(es_administrador)
def lista_usuarios(request):
    # Prefetch de grupos para evitar consultas N+1
    usuarios = ( UsuarioPersonalizado.objects.all().prefetch_related('groups').order_by('username'))
    context = {'usuarios': usuarios}
    return render(request, 'usuarios/lista_usuarios.html', context)

def registro_view(request):
    if request.method == 'POST':
        form = FormularioRegistro(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            return redirect('home')
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
            return redirect('home')
        else:
            return render(request, 'usuarios/login.html', {'error': 'Credenciales invalidas'})
    return render(request, 'usuarios/login.html')

@login_required
def home_view(request):
    es_admin = request.user.groups.filter(name='Administrador').exists()
    return render(request, 'usuarios/home.html', {'es_admin': es_admin})

def logout_view(request):
    logout(request)
    return redirect('login')