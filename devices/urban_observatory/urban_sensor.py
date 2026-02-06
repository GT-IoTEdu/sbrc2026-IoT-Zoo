#!/usr/bin/env python3
import pandas as pd
import time
import os
import json
import glob
import paho.mqtt.client as mqtt
from datetime import datetime
import sys
import gc

# --- CONFIGURATION ---
BROKER_ADDR = os.getenv('MQTT_BROKER_ADDR', '10.0.0.100')
TIME_SCALE = float(os.getenv('TIME_SCALE', '60.0')) 
DATA_DIR = '/data' 
TARGET_VAR = os.getenv('TARGET_VARIABLE', None)
BASE_TOPIC = os.getenv('MQTT_TOPIC_PUB', None)
CHUNK_SIZE = 5000  # Tamanho do lote que fica na RAM

print(f"--- STARTING GATEWAY {TARGET_VAR if TARGET_VAR else 'GENERAL'} (STREAMING MODE) ---")

# --- 1. MQTT CONNECTION (Conecta ANTES de ler os dados) ---
client = mqtt.Client(client_id=f"GW_{TARGET_VAR}_{int(time.time())}")
try:
    client.connect(BROKER_ADDR, 1883, 60)
    client.loop_start()
    print(f"[MQTT] Connected to Broker {BROKER_ADDR}")
except Exception as e:
    print(f"[MQTT] Fatal Connection Error: {e}")
    sys.exit(1)

# --- 2. FILE DISCOVERY ---
search_pattern = os.path.join(DATA_DIR, "**", "*.csv*")
all_files = glob.glob(search_pattern, recursive=True)
print(f"[Gateway] Files found: {len(all_files)}")

# Variável para controlar o tempo entre chunks diferentes
last_global_time = None

def classify_sensor(sid):
    sid_str = str(sid).upper()
    if 'MESH' in sid_str: return 'mesh'
    elif 'TTN' in sid_str: return 'ttn'
    elif 'PEOPLE' in sid_str: return 'urban_flow'
    else: return 'monitor'

# --- 3. STREAMING LOOP ---
for filename in all_files:
    if filename.endswith('.xz'): continue # Ignora compactados se já tiver CSV
    
    # Filtro rápido de nome de arquivo (igual ao original)
    if TARGET_VAR:
        fname_str = os.path.basename(filename).upper()
        target_str = str(TARGET_VAR).upper().replace('.', '').replace(' ', '')
        clean_fname = fname_str.replace('.CSV', '').replace('.', '').replace(' ', '')
        
        is_match = False
        if target_str in clean_fname: is_match = True
        elif "PARTICLE" in target_str and "PARTICLE" in fname_str: is_match = True
        elif "WALKING" in target_str and "PEDESTRIAN" in fname_str: is_match = True 
        elif "INTERNAL" in target_str and "INTERNAL" in fname_str: is_match = True
        elif "RAIN" in target_str and "RAIN" in fname_str: is_match = True
        
        if not is_match: continue 

    print(f"[Stream] Reading {filename}...", flush=True)

    try:
        # Lê o arquivo em pedaços (Iterador)
        chunk_iter = pd.read_csv(filename, parse_dates=['Timestamp'], chunksize=CHUNK_SIZE)

        for i, chunk in enumerate(chunk_iter):
            # Normalização de Colunas
            chunk.columns = chunk.columns.str.strip().str.upper()
            rename_map = {
                'TIMESTAMP': 'Timestamp', 'UNITS': 'Unit', 'UNIT': 'Unit',
                'VARIABLE': 'Variable', 'VALUE': 'Value', 'READING': 'Value', 
                'COUNT': 'Value', 'PEDESTRIAN COUNT': 'Value', 'WALKING': 'Value',
                'LATITUDE': 'Latitude', 'LONGITUDE': 'Longitude',
                'SENSOR NAME': 'sensor_id', 'SENSORNAME': 'sensor_id', 'SITE': 'sensor_id', 'NAME': 'sensor_id'
            }
            chunk.rename(columns=rename_map, inplace=True)

            # Filtra linhas inúteis DENTRO do chunk
            if TARGET_VAR and 'Variable' in chunk.columns:
                chunk = chunk[chunk['Variable'].astype(str).str.contains(TARGET_VAR, case=False, na=False)]
            
            if chunk.empty: continue

            # Garante ordenação LOCAL (dentro do chunk)
            if 'Timestamp' in chunk.columns:
                chunk.sort_values(by='Timestamp', inplace=True)

            # Preenche dados faltantes
            if 'sensor_id' not in chunk.columns:
                chunk['sensor_id'] = os.path.basename(filename).replace('.csv', '')
            if 'Unit' not in chunk.columns: chunk['Unit'] = "N/A"
            if 'Variable' not in chunk.columns: chunk['Variable'] = TARGET_VAR if TARGET_VAR else "Unknown"

            # --- PLAYBACK LOOP (Processa linha por linha) ---
            print(f"[Stream] Sending Chunk {i} ({len(chunk)} rows)...")
            
            for index, row in chunk.iterrows():
                current_time = row.get('Timestamp')
                
                # Lógica de Sleep (Mantém coerência entre chunks)
                if last_global_time is not None and isinstance(current_time, datetime):
                    time_diff = (current_time - last_global_time).total_seconds()
                    if time_diff > 0:
                        sleep_duration = time_diff / TIME_SCALE
                        # Cap para evitar dormir dias se houver buraco nos dados
                        if sleep_duration > 5: sleep_duration = 5 
                        if sleep_duration > 0.001:
                            time.sleep(sleep_duration)
                
                if isinstance(current_time, datetime):
                    last_global_time = current_time

                # Monta Payload
                val = row.get('Value', 0)
                if pd.isna(val): val = 0
                
                payload = {
                    "sensor_id": row['sensor_id'],
                    "infra_type": classify_sensor(row['sensor_id']), 
                    "variable": str(row.get('Variable', 'Unknown')),
                    "value": val,
                    "unit": str(row.get('Unit', '')),
                    "location": {"lat": row.get('Latitude', 0), "lon": row.get('Longitude', 0)},
                    "ts_orig": str(current_time),
                    "ts_sent": str(datetime.now())
                }

                # Define Tópico
                if BASE_TOPIC:
                    topic = f"{BASE_TOPIC}/{row['sensor_id']}"
                else:
                    var_slug = str(payload['variable']).lower().replace(' ', '').replace('.', '')[:15]
                    topic = f"city/air_quality/{payload['infra_type']}/{var_slug}/{row['sensor_id']}"

                client.publish(topic, json.dumps(payload))

            # Limpeza manual de memória para garantir
            del chunk
            gc.collect()

    except Exception as e:
        print(f"[Error] Stream failed for {filename}: {e}")

# Mantém o container vivo se acabar os dados
print("[Gateway] All files processed. Idling...")
while True: time.sleep(100)
