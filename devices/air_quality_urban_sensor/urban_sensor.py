import pandas as pd
import time
import json
import os
import paho.mqtt.client as mqtt
from datetime import datetime

# --- CONFIGURAÇÕES ---
BROKER_ADDR = os.getenv('MQTT_BROKER_ADDR', '192.168.159.1')
TOPIC_BASE = os.getenv('MQTT_TOPIC', 'city/air_quality')

# O container sempre lê deste caminho fixo
CSV_FILE = '/data.csv.xz' 

# Aceleração (60x: 1 minuto no CSV = 1 segundo na vida real)
TIME_SCALE = float(os.getenv('TIME_SCALE', '60.0')) 

print(f"--- INICIANDO SENSOR URBANO (Time Scale: {TIME_SCALE}x) ---")

# 1. Carregar CSV
try:
    # Lendo apenas colunas essenciais
    df = pd.read_csv(CSV_FILE, parse_dates=['Timestamp'])
    df = df.sort_values(by='Timestamp')
    print(f"Dados carregados: {len(df)} amostras.")
except Exception as e:
    print(f"Erro crítico ao ler CSV: {e}")
    print("Verifique se o volume foi montado corretamente em /data.csv")
    exit(1)

# Pega o ID do sensor da primeira linha do arquivo
SENSOR_ID = df.iloc[0]['Sensor Name']
print(f"Identidade do Sensor detectada: {SENSOR_ID}")

# 2. Conectar MQTT
client = mqtt.Client(client_id=SENSOR_ID)
conectado = False

print(f"Tentando conectar ao Broker {BROKER_ADDR}...")

while not conectado:
    try:
        client.connect(BROKER_ADDR, 1883, 60)
        print(f"✅ Conectado com sucesso!")
        conectado = True
    except Exception as e:
        print(f"⏳ Falha na conexão ({e}). Tentando novamente em 5s...")
        time.sleep(5)

# 3. Loop de Envio
records = df.to_dict('records')

for i in range(len(records)):
    row = records[i]
    
    # Monta o Payload JSON
    payload = {
        "sensor_id": row['Sensor Name'],
        "variable": row['Variable'],
        "value": float(row['Value']),
        "unit": row['Units'],
        "location": {
            "lat": row['Sensor Centroid Latitude'],
            "lon": row['Sensor Centroid Longitude']
        },
        "ts_orig": str(row['Timestamp']),
        "ts_sent": str(datetime.now())
    }
    
    # Publica
    topic = f"{TOPIC_BASE}/{SENSOR_ID}"
    try:
        client.publish(topic, json.dumps(payload))
        print(f"[>>] Enviado: {payload['value']} {payload['unit']}")
    except Exception as e:
        print(f"[xx] Erro ao publicar: {e}")
        # Se cair a conexão aqui, o paho-mqtt tenta reconectar sozinho no próximo loop
    
    # Espera (Baseada no Timestamp real)
    if i < len(records) - 1:
        next_row = records[i+1]
        delta = (next_row['Timestamp'] - row['Timestamp']).total_seconds()
        
        # Aplica escala temporal
        sleep_time = delta / TIME_SCALE
        
        if sleep_time > 0:
            time.sleep(sleep_time)

print("--- FIM DO DATASET ---")
