import pandas as pd

FILE_NAME = "2025-PM10.csv"

print(f"--- INICIANDO ANÁLISE DE: {FILE_NAME} ---")
print("Carregando arquivo...")


try:
    df = pd.read_csv(FILE_NAME, parse_dates=['Timestamp'])
except ValueError:
    print("Aviso: Convertendo datas manualmente...")
    df = pd.read_csv(FILE_NAME)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])

print(f"Total de linhas carregadas: {len(df)}")

sensores_unicos = df['Sensor Name'].unique()
qtd_sensores = len(sensores_unicos)
print(f"\n>>> Quantidade de Dispositivos (Sensores) Únicos: {qtd_sensores}")


print("\n>>> Analisando frequência de cada sensor (Aguarde...)\n")

resultados = []


for sensor_name, grupo in df.groupby('Sensor Name'):
    grupo = grupo.sort_values('Timestamp')
    
    total_amostras = len(grupo)
    
    intervalos = grupo['Timestamp'].diff().dropna()
    
    if len(intervalos) > 0:
        media_intervalo = intervalos.mean()
        moda_intervalo = intervalos.mode()[0] # O intervalo mais comum
        min_intervalo = intervalos.min()
        max_intervalo = intervalos.max()
    else:
        media_intervalo = pd.Timedelta(0)
        moda_intervalo = pd.Timedelta(0)
        min_intervalo = pd.Timedelta(0)
        max_intervalo = pd.Timedelta(0)
        
    resultados.append({
        'Sensor': sensor_name,
        'Amostras': total_amostras,
        'Freq_Mais_Comum': moda_intervalo,
        'Freq_Media': media_intervalo,
        'Inicio': grupo['Timestamp'].min(),
        'Fim': grupo['Timestamp'].max()
    })

resumo = pd.DataFrame(resultados)
resumo = resumo.sort_values(by='Amostras', ascending=False)

print("-" * 120)
print(f"{'SENSOR NAME':<30} | {'AMOSTRAS':<10} | {'FREQ. PADRÃO (MODA)':<25} | {'FREQ. MÉDIA':<25}")
print("-" * 120)

for index, row in resumo.head(20).iterrows():
    print(f"{row['Sensor']:<30} | {str(row['Amostras']):<10} | {str(row['Freq_Mais_Comum']):<25} | {str(row['Freq_Media']):<25}")

print("-" * 120)
print(f"\nResumo Geral:")
print(f"Sensor com MAIS dados: {resumo.iloc[0]['Sensor']} ({resumo.iloc[0]['Amostras']} amostras)")
print(f"Sensor com MENOS dados: {resumo.iloc[-1]['Sensor']} ({resumo.iloc[-1]['Amostras']} amostras)")
