from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import EventoDeAcceso

@login_required
def dashboard_anomalias(request):
    # Buscamos en la BD solo los eventos marcados como anomalias (es_anomalias=True)
    anomalias = EventoDeAcceso.objects.filter(es_anomalia=True)

    context={
        'anomalias': anomalias,
        'total_anomalias': anomalias.count(),
    }

    # Renderizamos la plantilla HTML con los datos de anomalias
    return render(request, 'monitoreo/dashboard.html', context)