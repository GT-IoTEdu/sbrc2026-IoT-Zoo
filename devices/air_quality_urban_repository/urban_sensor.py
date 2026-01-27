#!/usr/bin/env python3
import pandas as pd
import time
import os
import json
import glob
import paho.mqtt.client as mqtt
from datetime import datetime
import sys

BROKER_ADDR = os.getenv('MQTT_BROKER_ADDR', '10.0.0.100')
TIME_SCALE = float(os.getenv('TIME_SCALE', '60.0')) 
DATA_DIR = '/data' 
# Variável Alvo (Ex: 'CO', 'NO2'). Se None, tenta pegar tudo (não recomendado para gateways separados)
TARGET_VAR = os.getenv('TARGET_VARIABLE', None)

print(f"--- INICIANDO GATEWAY {TARGET_VAR if TARGET_VAR else 'GERAL'} (Scale: {TIME_SCALE}x) ---")

all_files = glob.glob(os.path.join(DATA_DIR, "*.csv*"))
print(f"[Gateway] Arquivos encontrados na pasta: {len(all_files)}")

df_list = []

for filename in all_files:
    if TARGET_VAR:
        fname_str = os.path.basename(filename).upper()
        target_str = str(TARGET_VAR).upper().replace('.', '').replace(' ', '')

        if target_str not in fname_str.replace('.', '').replace(' ', '') and "PARTICLE" not in fname_str:
             pass 

    try:
        temp_df = pd.read_csv(filename, parse_dates=['Timestamp'])
        
        temp_df.columns = temp_df.columns.str.strip().str.upper()
        
        rename_map = {
            'UNITS': 'Unit', 'UNIT': 'Unit',
            'VARIABLE': 'Variable',
            'VALUE': 'Value',
            'LATITUDE': 'Latitude', 'LONGITUDE': 'Longitude',
            'SENSOR NAME': 'sensor_id', 
            'SENSORNAME': 'sensor_id',
            'SITE': 'sensor_id',
            'NAME': 'sensor_id'
        }
        temp_df.rename(columns=rename_map, inplace=True)
        
        if TARGET_VAR:
            if 'Variable' in temp_df.columns:
                temp_df = temp_df[temp_df['Variable'].astype(str).str.contains(TARGET_VAR, case=False, na=False)]
        
        if temp_df.empty:
            continue

        if 'sensor_id' not in temp_df.columns:
            basename = os.path.basename(filename).replace('.csv.xz', '').replace('.csv', '')
            temp_df['sensor_id'] = basename
        
        def classify_sensor(sid):
            sid_str = str(sid).upper()
            if 'MESH' in sid_str:
                return 'mesh'      # Sensores Urbanos Mesh
            elif 'TTN' in sid_str:
                return 'ttn'       # The Things Network (LoRa)
            else:
                return 'monitor'   # Reference/Monitor Stations
        
        temp_df['sensor_type'] = temp_df['sensor_id'].apply(classify_sensor)

        if 'Unit' not in temp_df.columns: temp_df['Unit'] = "N/A"
        if 'Variable' not in temp_df.columns: temp_df['Variable'] = "Unknown"
        
        cols_to_keep = ['Timestamp', 'Variable', 'Value', 'Unit', 'Latitude', 'Longitude', 'sensor_id', 'sensor_type']
        existing_cols = [c for c in cols_to_keep if c in temp_df.columns]
        temp_df = temp_df[existing_cols]
        
        df_list.append(temp_df)
    except Exception as e:
        pass

if not df_list:
    print(f"[Aviso] Gateway {TARGET_VAR}: Nenhum dado encontrado. Entrando em espera...")
    while True: time.sleep(100)

print("[Gateway] Fundindo e ordenando dados...")
master_df = pd.concat(df_list, ignore_index=True)
master_df.sort_values(by='Timestamp', inplace=True)
master_df.reset_index(drop=True, inplace=True)

print(f"[Gateway] {len(master_df)} registros carregados para {TARGET_VAR}.")

# Conexão MQTT
client = mqtt.Client(client_id=f"GW_{TARGET_VAR if TARGET_VAR else 'Main'}_{int(time.time())}")
try:
    client.connect(BROKER_ADDR, 1883, 60)
    client.loop_start()
    print(f"[MQTT] Conectado ao Broker {BROKER_ADDR}")
except Exception as e:
    print(f"[MQTT] Erro Fatal: {e}")
    exit(1)

# Loop de Reprodução
last_time = master_df['Timestamp'].iloc[0]

for index, row in master_df.iterrows():
    current_time = row['Timestamp']
    time_diff = (current_time - last_time).total_seconds()
    
    if time_diff > 0:
        sleep_duration = time_diff / TIME_SCALE
        if sleep_duration > 0.001:
            time.sleep(sleep_duration)
    
    last_time = current_time
    
    val = row.get('Value', 0)
    unit = row.get('Unit', '')
    if pd.isna(val): val = 0
    if pd.isna(unit): unit = ""
    
    payload = {
        "sensor_id": row['sensor_id'],
        "type": row['sensor_type'],
        "variable": row.get('Variable', 'Unknown'),
        "value": val,
        "unit": unit,
        "location": {
            "lat": row.get('Latitude', 0), 
            "lon": row.get('Longitude', 0)
        },
        "ts_orig": str(current_time),
        "ts_sent": str(datetime.now())
    }
    
    var_slug = "gen"
    if 'Variable' in row and row['Variable']:
        var_slug = str(row['Variable']).lower().replace(' ', '').replace('.', '')
        # Pega so os primeiros 10 chars pra nao ficar gigante
        var_slug = var_slug[:10] 

    topic = f"city/air_quality/{row['sensor_type']}/{var_slug}/{row['sensor_id']}"
    
    client.publish(topic, json.dumps(payload))

    if index % 100 == 0:
        # print(f"[>>] {topic} -> {val}") # Descomente para debug
        pass

client.loop_stop()
