import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder
from .models import EventoDeAcceso
from django.utils import timezone  
from datetime import timedelta     

def ejecutar_deteccion_anomalias():
    """
    Obtiene todos los eventos de acceso de una "ventana de tiempo" (ej. 180 días),
    los procesa y usa Isolation Forest para marcar anomalías.
    """
    
    # --- INICIO DE LA LÓGICA DE VENTANA DE TIEMPO ---
    
    # 1. Definir la ventana de análisis
    # ¡Aquí está la variable! La ponemos en 180 para que analice
    # todos los datos históricos que acabamos de cargar.
    DIAS_DE_VENTANA = 180 
    fecha_limite = timezone.now() - timedelta(days=DIAS_DE_VENTANA)

    print(f"Iniciando detección de anomalías para los últimos {DIAS_DE_VENTANA} días...")

    # 2. Obtener SÓLO los eventos dentro de esa ventana de tiempo.
    eventos_en_ventana = EventoDeAcceso.objects.filter(timestamp__gte=fecha_limite)
    total_eventos = eventos_en_ventana.count()

    # 3. Reiniciar las marcas SÓLO para los eventos dentro de esta ventana.
    # Esto soluciona el bug (275 vs 278) de forma eficiente.
    print(f"Se analizarán {total_eventos} eventos.")
    print("Reiniciando marcas de anomalías antiguas para esta ventana...")
    eventos_en_ventana.update(es_anomalia=False)
    
    # --- FIN DE LA LÓGICA DE VENTANA DE TIEMPO ---

    if total_eventos < 50: 
        print(f"No hay suficientes datos (se necesitan 50, hay {total_eventos}) para ejecutar la detección.")
        return 0

    # 1. Preparar datos con Pandas (ahora solo de la ventana)
    print("Cargando datos en Pandas...")
    df = pd.DataFrame(list(eventos_en_ventana.values()))
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # 2. Ingeniería de Características...
    print("Realizando ingeniería de características...")
    df['hora'] = df['timestamp'].dt.hour
    df['dia_de_semana'] = df['timestamp'].dt.dayofweek 

    # 3. Preprocesamiento...
    print("Realizando preprocesamiento (LabelEncoder)...")
    features_categoricos = ['email_usuario', 'direccion_ip', 'tipo_evento', 'archivo_id']
    for col in features_categoricos:
        if col in df.columns: # Asegurarse que la columna existe
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col])
        else:
            print(f"Advertencia: Columna {col} no encontrada en los datos recientes.")

    # 4. Entrenar el Modelo y Predecir...
    print("Entrenando modelo Isolation Forest y prediciendo...")
    features_para_modelo = ['email_usuario', 'direccion_ip', 'tipo_evento', 'archivo_id', 'hora', 'dia_de_semana']
    
    # Filtrar features que realmente existen en el DataFrame
    features_reales = [f for f in features_para_modelo if f in df.columns]
    
    # Ajustamos la contaminación. Con más datos, podemos ser más sensibles.
    # 0.05 (5%) de 25,000 es 1,250. Empecemos con algo más conservador: 1%
    modelo = IsolationForest(contamination=0.01, random_state=42) 
    predicciones = modelo.fit_predict(df[features_reales])

    # 5. Actualizar la Base de Datos
    print("Actualizando base de datos con nuevas anomalías...")
    df['es_anomalia'] = [True if p == -1 else False for p in predicciones]
    
    ids_anomalos = df[df['es_anomalia']]['id'].tolist()
    
    # Actualizamos solo los que SÍ son anomalías esta vez
    EventoDeAcceso.objects.filter(id__in=ids_anomalos).update(es_anomalia=True)
    
    print(f"Detección completada. Se marcaron {len(ids_anomalos)} eventos como anomalías.")
    return len(ids_anomalos)