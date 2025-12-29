import os
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import silhouette_score, davies_bouldin_score
from django.conf import settings
from django.utils import timezone
from datetime import timedelta     
from .models import EventoDeAcceso

def ejecutar_deteccion_anomalias():
    """
    SPRINT 5: Pipeline completo de Machine Learning.
    1. Preprocesamiento y Limpieza.
    2. Entrenamiento (Isolation Forest).
    3. Evaluación (Métricas de Silueta).
    4. Serialización (Guardado del modelo).
    5. Scoring y Persistencia en BD.
    """
    
    # --- 1. CONFIGURACIÓN Y CARGA DE DATOS ---
    DIAS_DE_VENTANA = 180 
    fecha_limite = timezone.now() - timedelta(days=DIAS_DE_VENTANA)

    print(f"\n🧠 [IA] Iniciando entrenamiento con ventana de {DIAS_DE_VENTANA} días...")

    eventos_qs = EventoDeAcceso.objects.filter(timestamp__gte=fecha_limite)
    total_eventos = eventos_qs.count()

    if total_eventos < 50:
        print(f"⚠️ [IA] Datos insuficientes ({total_eventos}). Se requieren mínimo 50.")
        return 0
    
    print(f"📊 [IA] Cargando {total_eventos} eventos en memoria...")

    # Convertir QuerySet a DataFrame
    df = pd.DataFrame(list(eventos_qs.values(
        'id', 'email_usuario', 'direccion_ip', 'tipo_evento', 'archivo_id', 'timestamp'
    )))
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # --- 2. INGENIERÍA DE CARACTERÍSTICAS (FEATURE ENGINEERING) ---
    print("🛠️ [IA] Preprocesando características...")

    # Extracción de características temporales (Normalización temporal)
    df['hora'] = df['timestamp'].dt.hour
    df['dia_de_semana'] = df['timestamp'].dt.dayofweek 

    # Codificación de variables categóricas
    encoders = {}
    features_categoricos = ['email_usuario', 'direccion_ip', 'tipo_evento', 'archivo_id']
    
    for col in features_categoricos:
        if col in df.columns: # Asegurarse que la columna existe
            le = LabelEncoder()
            # Convertimos a string para evitar errores con valores nulos
            df[col] = df[col].astype(str)
            df[col] = le.fit_transform(df[col])
            encoders[col] = le

    # Selección de features finales para el modelo
    features_modelo = ['email_usuario', 'direccion_ip', 'tipo_evento', 'archivo_id', 'hora', 'dia_de_semana']
    X = df[features_modelo]
    
    # --- 3. ENTRENAMIENTO DEL MODELO (TRAINING) ---
    print("🤖 [IA] Entrenando Isolation Forest (n_estimators=100, contamination=0.05)...")
    
    # Parámetros definidos en la propuesta
    modelo = IsolationForest(
        n_estimators=100,       # Número de árboles
        contamination=0.05,     # Esperamos un 5% de anomalías
        max_samples='auto',     # Muestreo automático
        random_state=42,        # Reproducibilidad
        n_jobs=-1               # Usar todos los núcleos del CPU (-1 es mejor rendimiento)
    ) 

    modelo.fit(X)

    # --- 4. EVALUACIÓN DEL MODELO (METRICS) ---
    try:
        # Usamos una muestra si hay demasiados datos para no congelar el equipo
        if len(X) > 20000:
            X_sample = X.sample(n=10000, random_state=42)
            labels_sample = modelo.predict(X_sample)

            # 1. Silueta (Silhouette Score)
            score_silueta = silhouette_score(X_sample, labels_sample)

            # 2. Davies-Bouldin Score
            score_db = davies_bouldin_score(X_sample, labels_sample)

        else:
            labels = modelo.predict(X)
            score_silueta = silhouette_score(X, labels)
            score_db = davies_bouldin_score(X, labels)

        print(f"📈 [IA] Métricas de Evaluación:")
        print(f"   - Silhouette Score: {score_silueta:.4f} (Mayor es mejor)")
        print(f"   - Davies-Bouldin:   {score_db:.4f} (Menor es mejor)")
    
    except Exception as e:
        print(f"⚠️ [IA] No se pudo calcular métrica de silueta: {e}")

    # --- 5. SERIALIZACIÓN (GUARDAR MODELOS) ---
    ruta_modelo = os.path.join(settings.BASE_DIR, 'monitoreo', 'ml_models')
    os.makedirs(ruta_modelo, exist_ok=True)
    archivo_pkl = os.path.join(ruta_modelo, 'isolation_forest.pkl')

    joblib.dump(modelo, archivo_pkl)
    print(f"💾 [IA] Modelo serializado guardado en: {archivo_pkl}")

    # --- 6. PREDICCIÓN Y SCORING ---
    print("🔍 [IA] Detectando anomalías y calculando scores...")

    # Predicción (-1 = Anomalía, 1 = Normal)
    predicciones = modelo.predict(X)

    # Score de anomalía (Valores negativos son más anómalos)
    scores_raw = modelo.decision_function(X)

    # Normalizamos el score para que quede bonito en el Dashboard (0 a 1)
    scores_normalizados = 0.5 - scores_raw 

    df['es_anomalia'] = [True if p == -1 else False for p in predicciones]
    df['anomaly_score'] = scores_normalizados

    # Filtrar solo las que resultaron anómalas para actualizar la BD
    anomalias_df = df[df['es_anomalia'] == True]
    
    ids_anomalos = anomalias_df['id'].tolist()

    # --- 7. PERSISTENCIA EN BASE DE DATOS ---
    print(f"📝 [IA] Actualizando {len(ids_anomalos)} eventos anómalos en BD...")

    # A. Limpiar marcas anteriores en la ventana (Reset)
    eventos_qs.update(es_anomalia=False, anomaly_score=0.0, severidad='BAJA')

    # B. Actualizar anomalías detectadas
    count = 0
    for index, row in anomalias_df.iterrows():
        try:
            evento = EventoDeAcceso.objects.get(id=row['id'])
            evento.es_anomalia = True
            evento.anomaly_score = float(row['anomaly_score'])

            # Asignar severidad basada en el score
            if evento.anomaly_score > 0.75:
                evento.severidad = 'CRITICA'
            elif evento.anomaly_score > 0.60:
                evento.severidad = 'ALTA'
            else:
                evento.severidad = 'MEDIA'

            evento.save() # Esto dispara signals si las hay
            count += 1

        except EventoDeAcceso.DoesNotExist:
            continue
    
    print(f"✅ [IA] Proceso finalizado. {count} anomalías registradas.")
    return count