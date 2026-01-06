#!/usr/bin/python
from mininet.net import Containernet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.log import info, setLogLevel
import os
import time

def fix_checksum(node):
    node.cmd('ethtool -K eth0 tx off > /dev/null 2>&1 || true')

def replay_topology():
    setLogLevel('info')
    # Limpeza
    os.system("docker rm -f mn.broker mn.predio mn.cooler mn.domotic mn.predictive > /dev/null 2>&1")

    net = Containernet(controller=Controller)
    net.addController('c0')

    BROKER_IP = "10.0.0.1"

    # 1. Broker (Usando a imagem corrigida do GothX)
    info(f'*** Adicionando Broker ({BROKER_IP})...\n')
    broker = net.addDocker('broker', ip=BROKER_IP, dimage="myzoo/mqtt_broker", dcmd="/bin/bash")

    # --- SENSORES COM DATASET ORIGINAL (Imagens myzoo) ---
    
    # A. Building Monitor (JSON)
    info('*** Adicionando Building Monitor...\n')
    predio = net.addDocker(
        'predio', ip="10.0.0.2", dimage="myzoo/building_monitor",
        environment={
            "MQTT_BROKER_ADDR": BROKER_IP,
            "MQTT_TOPIC_PUB": "building_data",
            "SLEEP_TIME": "5" # Envia a cada 5s (pode diminuir)
        },
        dcmd="/bin/bash" # Mantém vivo para iniciarmos manualmente
    )

    # B. Cooler Motor (Binário)
    info('*** Adicionando Cooler Motor...\n')
    cooler = net.addDocker(
        'cooler', ip="10.0.0.3", dimage="myzoo/cooler_motor",
        environment={"MQTT_BROKER_ADDR": BROKER_IP, "SLEEP_TIME": "5"},
        dcmd="/bin/bash"
    )

    # C. Domotic Monitor (XML)
    info('*** Adicionando Domotic Monitor...\n')
    domotic = net.addDocker(
        'domotic', ip="10.0.0.4", dimage="myzoo/domotic_monitor",
        environment={"MQTT_BROKER_ADDR": BROKER_IP, "SLEEP_TIME": "5"},
        dcmd="/bin/bash"
    )

    # D. Predictive Maintenance (JSON)
    info('*** Adicionando Predictive Maint...\n')
    predictive = net.addDocker(
        'predictive', ip="10.0.0.5", dimage="myzoo/predictive_maintenance",
        environment={"MQTT_BROKER_ADDR": BROKER_IP, "SLEEP_TIME": "5"},
        dcmd="/bin/bash"
    )

    # E. Air Quality (XML)
    info('*** Adicionando Air Quality...\n')
    air = net.addDocker(
        'air', ip="10.0.0.6", dimage="myzoo/air_quality",
        environment={"MQTT_BROKER_ADDR": BROKER_IP, "SLEEP_TIME": "5"},
        dcmd="/bin/bash"
    )
    
    # G. Camera
    # --- SISTEMA DE VÍDEO (CCTV) ---
    # IPs fixos para facilitar a configuração
    SERVER_IP = "10.0.0.20"
    CAM_IP = "10.0.0.21"
    CONS_IP = "10.0.0.22"
    
    info('*** Adicionando Sistema de Vídeo...\n')
    
    # 1. Servidor RTSP (O Gravador)
    video_server = net.addDocker(
        'v_server', ip=SERVER_IP, 
        dimage="myzoo/server_video", 
        dcmd="/bin/bash"
    )

    # 2. Câmera IP (Envia o vídeo para o servidor)
    camera = net.addDocker(
        'v_camera', ip=CAM_IP, 
        dimage="myzoo/camera",
        environment={
            "STREAM_SERVER_ADDR": SERVER_IP,
            "STREAM_SERVER_PORT": "8554",
            "STREAM_NAME": "live_feed",
            "VIDEO_FILE": "/video.mp4" 
        },
        dcmd="/bin/bash"
    )

    # 3. Consumidor (Assiste o vídeo para gerar tráfego)
    consumer = net.addDocker(
        'v_consumer', ip=CONS_IP, 
        dimage="myzoo/consumer_video",
        environment={
            "STREAM_SERVER_ADDR": SERVER_IP,
            "STREAM_SERVER_PORT": "8554",
            "STREAM_NAME": "live_feed",
            "ACTIVE_TIME": "60"
        },
        dcmd="/bin/bash"
    )
    
    # --- REDE ---
    info('*** Ligando a rede...\n')
    s1 = net.addSwitch('s1')
    net.addLink(broker, s1)
    net.addLink(predio, s1)
    net.addLink(cooler, s1)
    net.addLink(domotic, s1)
    net.addLink(predictive, s1)
    net.addLink(air, s1)
    net.addLink(video_server, s1)
    net.addLink(camera, s1)
    net.addLink(consumer, s1)
    net.start()

    # --- START ---
    info('*** Aplicando correções e iniciando...\n')
    for node in [broker, predio, cooler, domotic, predictive, air]:
        fix_checksum(node)
    
    broker.cmd('/usr/sbin/mosquitto -v > /tmp/broker.log 2>&1 &')
    
    # Iniciando os scripts originais (agora corrigidos)
    # Note: Não injetamos nada, usamos o script que já está na imagem (/client.py)
    predio.cmd('python3 -u /client.py > /tmp/predio.log 2>&1 &')
    cooler.cmd('python3 -u /client.py > /tmp/cooler.log 2>&1 &')
    domotic.cmd('python3 -u /client_bis.py > /tmp/domotic.log 2>&1 &') # Atenção ao _bis
    predictive.cmd('python3 -u /client.py > /tmp/predictive.log 2>&1 &')
    air.cmd('python3 -u /client.py > /tmp/air.log 2>&1 &')

    info('*** Aguardando conexões (5s)...\n')
    time.sleep(5)

    info('\n*** TESTE: Visualizando logs do Building Monitor:\n')
    print(predio.cmd('tail -n 5 /tmp/predio.log'))

    # CAMERA 1. Correção de Rede (Essencial para UDP de vídeo!)
    for node in [video_server, camera, consumer]:
        fix_checksum(node)

    # 2. Iniciar Servidor (Primeiro!)
    info('*** Iniciando Servidor de Vídeo...\n')
    video_server.cmd('/mediamtx /mediamtx.yml > /tmp/server.log 2>&1 &')
    
    time.sleep(2) # Dá um tempo para o servidor subir a porta 8554

    # 3. Iniciar Câmera e Consumidor
    info('*** Iniciando Streaming...\n')
    # A câmera começa a empurrar o vídeo
    camera.cmd('python3 -u /ip_camera.py > /tmp/cam.log 2>&1 &')
    # O consumidor começa a puxar o vídeo
    consumer.cmd('python3 -u /consume.py > /tmp/cons.log 2>&1 &')

    info('\n*** CLI Aberto. Teste: broker mosquitto_sub -t "#" -v\n')
    CLI(net)
    net.stop()

if __name__ == '__main__':
    replay_topology()
