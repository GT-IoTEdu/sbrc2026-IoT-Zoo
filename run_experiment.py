#!/usr/bin/python3
import argparse
import time
import os
import signal
import sys
from mininet.net import Containernet
from mininet.node import Controller
from mininet.log import info, setLogLevel
from mininet.nodelib import NAT

DEFAULT_TIME = 60
DEFAULT_PCAP = "capture.pcap"
# [CAMINHO ATUALIZADO]
PATH_TO_DATASET = "/home/vagner/virtual-testbed/devices/air_quality_urban_repository"

# [LISTA EXATA DE VARIÁVEIS BASEADA NOS SEUS ARQUIVOS]
# O script cria um container para cada item desta lista.
URBAN_VARIABLES = [
    "CO", 
    "NO2", 
    "NO", 
    "NOx", 
    "O3", 
    "Particle", # Para ler o '2025-Particle Count.csv.xz'
    "PM1",      # Cuidado: PM1 pode dar match em PM10, mas o script tenta ser exato
    "PM10", 
    "PM2.5", 
    "PM 4"      # Note o espaço, igual ao nome do arquivo
]

def stop_simulation(net, pcap_process=None):
    info('\n*** Encerrando experimento...\n')
    if pcap_process:
        pcap_process.send_signal(signal.SIGINT)
        pcap_process.wait()
    if net:
        net.stop()
    os.system("docker rm -f $(docker ps -aq --filter name=mn) > /dev/null 2>&1")
    info('*** Limpeza concluída.\n')
    sys.exit(0)

def fix_checksum(node):
    node.cmd('ethtool -K eth0 tx off > /dev/null 2>&1 || true')
    node.cmd('ethtool -K nat0-eth0 tx off > /dev/null 2>&1 || true')

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--time', type=int, default=DEFAULT_TIME)
    parser.add_argument('-o', '--output', type=str, default=DEFAULT_PCAP)
    args = parser.parse_args()
    
    pcap_path = os.path.abspath(args.output)
    setLogLevel('info')
    
    os.system("docker rm -f $(docker ps -aq --filter name=mn) > /dev/null 2>&1")

    net = Containernet(controller=Controller)
    net.addController('c0')
    
    BROKER_INT_IP = "10.0.0.100"
    
    info(f'*** Iniciando Experimento IoT-IDS (Multi-Gateway .xz)\n')

    # Infra
    broker = net.addDocker('broker', ip=BROKER_INT_IP, dimage="myzoo/mqtt_broker", dcmd="/bin/bash")

    # Dispositivos Clássicos (IPs 10.0.0.2 - 10.0.0.7)
    predio = net.addDocker('predio', ip="10.0.0.2", dimage="myzoo/building_monitor",
        environment={"MQTT_BROKER_ADDR": BROKER_INT_IP, "MQTT_TOPIC_PUB": "building", "SLEEP_TIME": "5"}, dcmd="/bin/bash")
    cooler = net.addDocker('cooler', ip="10.0.0.3", dimage="myzoo/cooler_motor",
        environment={"MQTT_BROKER_ADDR": BROKER_INT_IP, "SLEEP_TIME": "5"}, dcmd="/bin/bash")
    domotic = net.addDocker('domotic', ip="10.0.0.4", dimage="myzoo/domotic_monitor",
        environment={"MQTT_BROKER_ADDR": BROKER_INT_IP, "SLEEP_TIME": "5"}, dcmd="/bin/bash")
    predictive = net.addDocker('predictive', ip="10.0.0.5", dimage="myzoo/predictive_maintenance",
        environment={"MQTT_BROKER_ADDR": BROKER_INT_IP, "SLEEP_TIME": "5"}, dcmd="/bin/bash")
    air = net.addDocker('air', ip="10.0.0.6", dimage="myzoo/air_quality",
        environment={"MQTT_BROKER_ADDR": BROKER_INT_IP, "SLEEP_TIME": "5"}, dcmd="/bin/bash")
    patient1 = net.addDocker('patient1', ip="10.0.0.7", dimage="myzoo/mhealth",
        environment={"MQTT_BROKER_ADDR": BROKER_INT_IP, "MQTT_TOPIC_PUB": "hospital/patients", "SUBJECT_ID": "1", "SPEED_FACTOR": "0.02"}, dcmd="/client.py")

    # [CRIAÇÃO DOS GATEWAYS]
    gateways = []
    base_ip = 50
    
    for var in URBAN_VARIABLES:
        clean_var_name = var.lower().replace('.', '').replace(' ', '')[:4]
        
        gw_name = f"gw_{clean_var_name}"
        gw_ip = f"10.0.0.{base_ip}"
        
        if any(g.name == gw_name for g in gateways):
            gw_name = f"{gw_name}_{base_ip}"

        info(f'*** Gateway {gw_name} ({gw_ip}) -> Monitorando {var}\n')
        
        gw = net.addDocker(gw_name, ip=gw_ip, dimage="myzoo/urban_sensor",
            volumes=[f"{PATH_TO_DATASET}:/data:ro"], 
            environment={
                "MQTT_BROKER_ADDR": BROKER_INT_IP, 
                "TIME_SCALE": "60.0",
                "TARGET_VARIABLE": var 
            }, dcmd="/bin/bash")
        
        gateways.append(gw)
        base_ip += 1

    # CCTV
    v_server = net.addDocker('v_server', ip="10.0.0.20", dimage="myzoo/server_video", dcmd="/bin/bash")
    v_camera = net.addDocker('v_camera', ip="10.0.0.21", dimage="myzoo/camera",
        environment={"STREAM_SERVER_ADDR": "10.0.0.20", "STREAM_SERVER_PORT": "8554", "STREAM_NAME": "live", "VIDEO_FILE": "/video.mp4"}, dcmd="/bin/bash")
    v_consumer = net.addDocker('v_consumer', ip="10.0.0.22", dimage="myzoo/consumer_video",
        environment={"STREAM_SERVER_ADDR": "10.0.0.20", "STREAM_SERVER_PORT": "8554", "STREAM_NAME": "live", "ACTIVE_TIME": str(args.time)}, dcmd="/bin/bash")

    s1 = net.addSwitch('s1')
    
    all_nodes = [broker, predio, cooler, domotic, predictive, air, patient1, v_server, v_camera, v_consumer] + gateways
    
    for node in all_nodes:
        net.addLink(node, s1)
    
    nat = net.addNAT(name='nat0', ip='10.0.0.254')
    net.addLink(nat, s1)

    info('*** Iniciando Rede...\n')
    net.start()

    for node in all_nodes:
        node.cmd('ip route del default 2> /dev/null') 
        node.cmd('ip route add default via 10.0.0.254')
        fix_checksum(node)
    fix_checksum(nat)

    info(f'*** Iniciando tcpdump...\n')
    s1.cmd(f"tcpdump -i any -w {pcap_path} -U not port 6653 &")

    info('*** Iniciando Serviços...\n')
    broker.cmd('/usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf -d &')
    v_server.cmd('/mediamtx /mediamtx.yml > /dev/null 2>&1 &')
    time.sleep(3)

    predio.cmd('python3 -u /client.py > /dev/null 2>&1 &')
    cooler.cmd('python3 -u /client.py > /dev/null 2>&1 &')
    domotic.cmd('python3 -u /client_bis.py > /dev/null 2>&1 &') 
    predictive.cmd('python3 -u /client.py > /dev/null 2>&1 &')
    air.cmd('python3 -u /client.py > /dev/null 2>&1 &')
    patient1.cmd('python3 -u /client.py > /dev/null 2>&1 &')
    
    v_camera.cmd('python3 -u /ip_camera.py > /dev/null 2>&1 &')
    v_consumer.cmd('python3 -u /consume.py > /dev/null 2>&1 &')
    
    # Inicia os Gateways (logs individuais em /tmp)
    for gw in gateways:
        gw.cmd(f'python3 -u /urban_sensor.py > /tmp/{gw.name}.log 2>&1 &')

    info(f'*** Rodando simulação por {args.time}s...\n')
    try:
        start_time = time.time()
        while (time.time() - start_time) < args.time:
            remaining = int(args.time - (time.time() - start_time))
            sys.stdout.write(f"\rTempo restante: {remaining}s   ")
            sys.stdout.flush()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        stop_simulation(net, None)

if __name__ == '__main__':
    run()
