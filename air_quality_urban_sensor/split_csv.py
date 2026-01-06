import pandas as pd
import os

FILE_NAME = "2025-PM10.csv"
OUTPUT_DIR = "dataset_splited"

print(f"Lendo {FILE_NAME}...")
# Lemos apenas colunas uteis
cols = ['Sensor Name', 'Variable', 'Units', 'Timestamp', 'Value', 'Sensor Centroid Latitude', 'Sensor Centroid Longitude']
df = pd.read_csv(FILE_NAME, usecols=cols, parse_dates=['Timestamp'])

# Cria pasta de saida
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Separa por sensor
print("Separando arquivos...")
for sensor_name, data in df.groupby('Sensor Name'):
    # Limpa nome do arquivo (remove caracteres estranhos se houver)
    safe_name = "".join([c for c in sensor_name if c.isalnum() or c in (' ', '_')]).strip()
    outfile = f"{OUTPUT_DIR}/{safe_name}.csv"
    
    # Salva ordenado por tempo
    data.sort_values('Timestamp').to_csv(outfile, index=False)
    print(f"-> Salvo: {outfile} ({len(data)} linhas)")

print("\nConcluído! Dados prontos para os containers.")
