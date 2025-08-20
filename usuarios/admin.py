from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from . models import UsuarioPersonalizado

# Register your models here.
admin.site.register(UsuarioPersonalizado, UserAdmin)
