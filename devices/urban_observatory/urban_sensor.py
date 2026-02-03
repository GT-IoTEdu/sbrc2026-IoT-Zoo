#!/usr/bin/env python3
import pandas as pd
import time
import os
import json
import glob
import paho.mqtt.client as mqtt
from datetime import datetime
import sys

# --- CONFIGURATION ---
BROKER_ADDR = os.getenv('MQTT_BROKER_ADDR', '10.0.0.100')
TIME_SCALE = float(os.getenv('TIME_SCALE', '60.0')) 
DATA_DIR = '/data' 
TARGET_VAR = os.getenv('TARGET_VARIABLE', None)
BASE_TOPIC = os.getenv('MQTT_TOPIC_PUB', None)
CHUNK_SIZE = 10000  # Reads 10k rows at a time to save RAM

print(f"--- STARTING GATEWAY {TARGET_VAR if TARGET_VAR else 'GENERAL'} ---")
print(f"--- Config: Scale={TIME_SCALE}x | Broker={BROKER_ADDR} | Topic={BASE_TOPIC if BASE_TOPIC else 'Auto'} ---")

search_pattern = os.path.join(DATA_DIR, "**", "*.csv*")
all_files = glob.glob(search_pattern, recursive=True)
print(f"[Gateway] Files found in folder tree: {len(all_files)}")

df_list = []

for filename in all_files:
    # 1. OPTIMIZATION: Skip .xz if .csv exists
    if filename.endswith('.xz'):
        uncompressed_version = filename.replace('.xz', '')
        if os.path.exists(uncompressed_version):
            continue 
            
    # 2. FILENAME FILTERING (Fast check)
    if TARGET_VAR:
        fname_str = os.path.basename(filename).upper()
        target_str = str(TARGET_VAR).upper().replace('.', '').replace(' ', '')
        clean_fname = fname_str.replace('.CSV.XZ', '').replace('.CSV', '').replace('.', '').replace(' ', '')

        is_match = False
        if target_str in clean_fname: is_match = True
        elif "PARTICLE" in target_str and "PARTICLE" in fname_str: is_match = True
        elif "WALKING" in target_str and "PEDESTRIAN" in fname_str: is_match = True 
        elif "INTERNAL" in target_str and "INTERNAL" in fname_str: is_match = True
        elif "RAIN" in target_str and "RAIN" in fname_str: is_match = True
            
        if not is_match:
             continue 

    print(f"[DEBUG] Match found! Reading file in CHUNKS: {filename}...", flush=True)
    
    try:
        # --- CHUNKING IMPLEMENTATION ---
        # Instead of reading the whole file, we get an iterator
        chunk_iter = pd.read_csv(filename, parse_dates=['Timestamp'], chunksize=CHUNK_SIZE)
        
        chunks_kept = 0
        
        # Added 'enumerate' to get the chunk index for the print
        for i, chunk in enumerate(chunk_iter):
            print(f"[DEBUG] Processing Chunk {i} ({len(chunk)} rows)...", flush=True)

            # Normalize columns to UPPERCASE
            chunk.columns = chunk.columns.str.strip().str.upper()
            
            rename_map = {
                'TIMESTAMP': 'Timestamp', # <--- A CORREÇÃO ESTÁ AQUI
                'UNITS': 'Unit', 'UNIT': 'Unit',
                'VARIABLE': 'Variable',
                'VALUE': 'Value', 'READING': 'Value', 'COUNT': 'Value', 'PEDESTRIAN COUNT': 'Value', 'WALKING': 'Value',
                'LATITUDE': 'Latitude', 'LONGITUDE': 'Longitude',
                'SENSOR NAME': 'sensor_id', 'SENSORNAME': 'sensor_id', 'SITE': 'sensor_id', 'NAME': 'sensor_id'
            }
            chunk.rename(columns=rename_map, inplace=True)
            
            # Filter rows by variable
            if TARGET_VAR and 'Variable' in chunk.columns:
                chunk = chunk[chunk['Variable'].astype(str).str.contains(TARGET_VAR, case=False, na=False)]
            
            if not chunk.empty:
                # Minimal processing for kept rows
                if 'sensor_id' not in chunk.columns:
                    basename = os.path.basename(filename).replace('.csv.xz', '').replace('.csv', '')
                    chunk['sensor_id'] = basename
                
                # Default Fills
                if 'Unit' not in chunk.columns: chunk['Unit'] = "N/A"
                if 'Variable' not in chunk.columns: chunk['Variable'] = TARGET_VAR if TARGET_VAR else "Unknown"
                
                # Keep only necessary columns to save RAM
                cols_to_keep = ['Timestamp', 'Variable', 'Value', 'Unit', 'Latitude', 'Longitude', 'sensor_id']
                existing_cols = [c for c in cols_to_keep if c in chunk.columns]
                chunk = chunk[existing_cols]
                
                df_list.append(chunk)
                chunks_kept += 1
        
        print(f"[DEBUG] Finished file. Kept {chunks_kept} useful chunks.")

    except Exception as e:
        print(f"[Error] Failed to read {filename}: {e}")
        pass

if not df_list:
    print(f"[Warning] Gateway {TARGET_VAR}: No data found in files (Check Variable Name!). Entering 'idle' mode...")
    while True: time.sleep(100)

print("[Gateway] Merging chunks...")
master_df = pd.concat(df_list, ignore_index=True)
# Agora vai funcionar porque 'Timestamp' foi preservado
master_df.sort_values(by='Timestamp', inplace=True)
master_df.reset_index(drop=True, inplace=True)

# Add Sensor Type (Post-process is lighter)
def classify_sensor(sid):
    sid_str = str(sid).upper()
    if 'MESH' in sid_str: return 'mesh'
    elif 'TTN' in sid_str: return 'ttn'
    elif 'ENVIRONMENT' in sid_str: return 'env_agency'
    elif 'WATER' in sid_str: return 'water_obs'
    elif 'EMLFLOOD' in sid_str: return 'flood_net'
    elif 'PEOPLE' in sid_str: return 'urban_flow'
    elif 'MET' in sid_str: return 'met_office'
    else: return 'monitor'

master_df['sensor_type'] = master_df['sensor_id'].apply(classify_sensor)

print(f"[Gateway] Ready! {len(master_df)} records loaded. Starting playback...")

# MQTT Connection
client = mqtt.Client(client_id=f"GW_{TARGET_VAR if TARGET_VAR else 'Gen'}_{int(time.time())}")
try:
    client.connect(BROKER_ADDR, 1883, 60)
    client.loop_start()
    print(f"[MQTT] Connected to Broker {BROKER_ADDR}")
except Exception as e:
    print(f"[MQTT] Fatal Connection Error: {e}")
    exit(1)

# Playback Loop
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
        "infra_type": row['sensor_type'], 
        "variable": str(row.get('Variable', 'Unknown')),
        "value": val,
        "unit": unit,
        "location": {
            "lat": row.get('Latitude', 0), 
            "lon": row.get('Longitude', 0)
        },
        "ts_orig": str(current_time),
        "ts_sent": str(datetime.now())
    }
    
    if BASE_TOPIC:
        topic = f"{BASE_TOPIC}/{row['sensor_id']}"
    else:
        var_slug = "gen"
        if 'Variable' in row and row['Variable']:
            var_slug = str(row['Variable']).lower().replace(' ', '').replace('.', '')[:15]
        topic = f"city/air_quality/{row['sensor_type']}/{var_slug}/{row['sensor_id']}"
    
    client.publish(topic, json.dumps(payload))

    if index % 1000 == 0:
        print(f"[>>] {topic}: {val} {unit}")

client.loop_stop()
