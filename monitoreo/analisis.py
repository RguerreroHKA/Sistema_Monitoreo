import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder
from .models import EventoDeAcceso

def ejecutar_deteccion_anomalias():
    """
        Obtiene todos los eventos de acceso, los procesa y usa Isolation Forest
        para marcar anomalías en la base de datos.
    """

    eventos = EventoDeAcceso.objects.all()
    if eventos.count() < 50: #Evitar entrenar con pocos datos
        print("No hay suficientes datos para entrenar la deteccion de anomalias.")
        return 0
    
    # 1. Preparar datos con Pandas
    df = pd.DataFrame(list(eventos.values()))
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # 2. Ingenieria de Caracteristicas: Crear Nuevas "pistas" para el modelo
    df['hora'] = df['timestamp'].dt.hour
    df['dia_de_semana'] = df['timestamp'].dt.dayofweek # Lunes=0, Domingo=6

    # 3. Preprocesamiento: Convertir texto a numeros con Label Encoding
    features_categoricos = ['email_usuario', 'direccion_ip', 'tipo_evento', 'archivo_id']
    for col in features_categoricos:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])

    # 4. Entrenar el Modelo y Predecir Anomalias
    features_para_modelo = ['email_usuario', 'direccion_ip', 'tipo_evento', 'archivo_id', 'hora', 'dia_de_semana']    
    # Contamination asume que ~5% de los datos son anomalias (40 de 840 es ~4.7%)
    modelo = IsolationForest(contamination=0.05, random_state=42)
    predicciones = modelo.fit_predict(df[features_para_modelo])

    # 5. Actualizar la Base de Datos 
    # El modelo devuelve -1 para anomalias y 1 para datos normales
    df['es_anomalia'] = [True if p == -1 else False for p in predicciones]

    # Actualizar en bloque solo los registros que son anomalias
    ids_anomalos = df[df['es_anomalia']]['id'].tolist()
    EventoDeAcceso.objects.filter(id__in=ids_anomalos).update(es_anomalia=True)

    print(f"Deteccion completada. Se marcaron {len(ids_anomalos)} evenotos comno anomalias")
    return len(ids_anomalos)
