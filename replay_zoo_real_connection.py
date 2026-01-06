#!/usr/bin/python
from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.log import info, setLogLevel
from mininet.nodelib import NAT
import os
import time

def fix_checksum(node):
    """Desliga o Checksum Offloading para evitar pacotes corrompidos no vSwitch"""
    # O NAT pode ter múltiplas interfaces, tentamos na padrão e na nat0-eth0
    node.cmd('ethtool -K eth0 tx off > /dev/null 2>&1 || true')
    node.cmd('ethtool -K nat0-eth0 tx off > /dev/null 2>&1 || true')

def hybrid_topology():
    setLogLevel('info')
    
    # 1. Limpeza preventiva
    os.system("docker rm -f mn.predio mn.cooler mn.domotic mn.predictive mn.air mn.u_mesh mn.u_ttn > /dev/null 2>&1")

    net = Containernet(controller=Controller)
    net.addController('c0')

    # --- CONFIGURAÇÃO HÍBRIDA ---
    # IP do computador Windows (Host) onde o Mosquitto está rodando
    BROKER_REAL_IP = "192.168.128.1" 
    
    PATH_TO_SPLIT_DATA = "/home/vagner/virtual-testbed/devices/air_quality_urban_sensor/dataset_splited"

    info(f'*** Configurando sensores para apontar para Broker Real: {BROKER_REAL_IP}\n')

    # --- SENSORES ---
    info('*** Adicionando Sensores...\n')
    
    # 1. Building Monitor (JSON)
    predio = net.addDocker(
        'predio', ip="10.0.0.2", dimage="myzoo/building_monitor",
        environment={"MQTT_BROKER_ADDR": BROKER_REAL_IP, "MQTT_TOPIC_PUB": "building", "SLEEP_TIME": "5"},
        dcmd="/bin/bash"
    )

    # 2. Cooler Motor (Binário)
    cooler = net.addDocker(
        'cooler', ip="10.0.0.3", dimage="myzoo/cooler_motor",
        environment={"MQTT_BROKER_ADDR": BROKER_REAL_IP, "SLEEP_TIME": "5"},
        dcmd="/bin/bash"
    )

    # 3. Domotic Monitor (XML)
    domotic = net.addDocker(
        'domotic', ip="10.0.0.4", dimage="myzoo/domotic_monitor",
        environment={"MQTT_BROKER_ADDR": BROKER_REAL_IP, "SLEEP_TIME": "5"},
        dcmd="/bin/bash"
    )

    # 4. Predictive Maintenance (JSON)
    predictive = net.addDocker(
        'predictive', ip="10.0.0.5", dimage="myzoo/predictive_maintenance",
        environment={"MQTT_BROKER_ADDR": BROKER_REAL_IP, "SLEEP_TIME": "5"},
        dcmd="/bin/bash"
    )

    # 5. Air Quality (XML)
    air = net.addDocker(
        'air', ip="10.0.0.6", dimage="myzoo/air_quality",
        environment={"MQTT_BROKER_ADDR": BROKER_REAL_IP, "SLEEP_TIME": "5"},
        dcmd="/bin/bash"
    )
    
    # --- SENSORES URBANOS (NEWCASTLE) ---
    info('*** Adicionando Sensores Urbanos (Newcastle)...\n')

    # Sensor 1: MESH (Alta Frequência - CSV específico montado como /data.csv)
    u_mesh = net.addDocker('u_mesh', ip="10.0.0.50", dimage="myzoo/urban_sensor",
        volumes=[f"{PATH_TO_SPLIT_DATA}/PER_AIRMON_MESH1907150.csv.xz:/data.csv.xz:ro"],
        environment={"MQTT_BROKER_ADDR": BROKER_REAL_IP, "TIME_SCALE": "60.0"},
        dcmd="/bin/bash")

    # Sensor 2: TTN (Baixa Frequência - CSV específico montado como /data.csv)
    u_ttn = net.addDocker('u_ttn', ip="10.0.0.51", dimage="myzoo/urban_sensor",
        volumes=[f"{PATH_TO_SPLIT_DATA}/PER_TTN_AIRQUALITY011.csv.xz:/data.csv.xz:ro"],
        environment={"MQTT_BROKER_ADDR": BROKER_REAL_IP, "TIME_SCALE": "60.0"},
        dcmd="/bin/bash")

    info('*** Adicionando Paciente Monitorado (MHEALTH)...\n')
    # Paciente 1 (Subject 1)
    patient1 = net.addDocker(
        'patient1', ip="10.0.0.60",
        dimage="myzoo/mhealth",
        environment={
            "MQTT_BROKER_ADDR": BROKER_REAL_IP,
            "MQTT_TOPIC_PUB": "hospital/patients", # Tópico base
            "SUBJECT_ID": "1",    # Lê o arquivo mHealth_subject1.log
            "SPEED_FACTOR": "0.02" # Acelera 5x
        },
        dcmd="/client.py"
    )
    # --- REDE COM SAÍDA (NAT) ---
    info('*** Adicionando Switch e NAT (Roteador de Saída)...\n')
    s1 = net.addSwitch('s1')
    
    # Conecta todos os sensores ao switch
    net.addLink(predio, s1)
    net.addLink(cooler, s1)
    net.addLink(domotic, s1)
    net.addLink(predictive, s1)
    net.addLink(air, s1)
    net.addLink(u_mesh, s1)
    net.addLink(u_ttn, s1)
    net.addLink(patient1, s1)
    
    # 1. Cria o NAT com IP fixo para servir de Gateway
    nat = net.addNAT(name='nat0', ip='10.0.0.254')
    
    # 2. Conecta o NAT ao Switch (criando o link físico virtual)
    net.addLink(nat, s1)

    info('*** Iniciando a Rede...\n')
    net.start()
    
    # --- CORREÇÃO DE ROTA (Gateway Padrão) ---
    info('*** Configurando Gateway Padrão (10.0.0.254) nos sensores...\n')
    all_sensors = [predio, cooler, domotic, predictive, air, u_mesh, u_ttn, patient1]
    for node in all_sensors:
        # Remove qualquer rota padrão antiga (se houver)
        node.cmd('ip route del default 2> /dev/null') 
        # Adiciona a rota correta apontando para o NAT
        node.cmd('ip route add default via 10.0.0.254')
        
    # 3. Configura as rotas padrão nos hosts para usarem o NAT como gateway
    nat.configDefault()

    # --- START ---
    info('*** Aplicando correções de rede (Checksum)...\n')
    nodes = [predio, cooler, domotic, predictive, air, u_mesh, u_ttn, patient1, nat]
    for node in nodes:
        fix_checksum(node)
    
    info('*** Verificando conectividade externa...\n')
    # Teste de ping rápido: O sensor consegue ver o computador?
    ping_result = predio.cmd(f'ping -c 1 {BROKER_REAL_IP}')
    if "0% packet loss" in ping_result:
        info("✅ Conectividade com Host Windows OK!\n")
    else:
        info(f"⚠️ AVISO: Sensor não conseguiu pingar {BROKER_REAL_IP}. Verifique o Firewall do Windows!\n")

    info('*** Iniciando scripts dos sensores...\n')

    predio.cmd('python3 -u /client.py > /tmp/predio.log 2>&1 &')
    cooler.cmd('python3 -u /client.py > /tmp/cooler.log 2>&1 &')
    domotic.cmd('python3 -u /client_bis.py > /tmp/domotic.log 2>&1 &') 
    predictive.cmd('python3 -u /client.py > /tmp/predictive.log 2>&1 &')
    air.cmd('python3 -u /client.py > /tmp/air.log 2>&1 &')
    
    # Scripts Urbanos
    u_mesh.cmd('python3 -u /urban_sensor.py > /tmp/mesh.log 2>&1 &')
    u_ttn.cmd('python3 -u /urban_sensor.py > /tmp/ttn.log 2>&1 &')
    patient1.cmd('python3 -u /client.py > /tmp/patient1.log 2>&1 &')

    info('*** Aguardando dados (10s)...\n')
    time.sleep(10)

    info('\n*** DIAGNÓSTICO (Building Monitor):\n')
    print(predio.cmd('tail -n 5 /tmp/predio.log'))
    
    info('\n*** DIAGNÓSTICO (Urban Mesh):\n')
    print(u_mesh.cmd('tail -n 5 /tmp/mesh.log'))
    
    info('\n*** DIAGNÓSTICO (Urban TTN):\n')
    print(u_ttn.cmd('tail -n 5 /tmp/ttn.log'))

    info('\n*** DIAGNÓSTICO (Patient 1):\n')
    print(patient1.cmd('tail -n 5 /tmp/patient1.log'))
    
    info('\n*** MODO HÍBRIDO ATIVO ***')
    info(f'Monitore o Mosquitto no Windows (IP {BROKER_REAL_IP})!\n')
    
    CLI(net)
    net.stop()

if __name__ == '__main__':
    hybrid_topology()
