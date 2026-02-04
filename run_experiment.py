#!/usr/bin/python3
import argparse
import time
import os
import signal
import sys
import glob
import subprocess
from mininet.net import Containernet
from mininet.node import Controller
from mininet.log import info, setLogLevel
from mininet.nodelib import NAT

DEFAULT_TIME = 60
DEFAULT_PCAP = "capture.pcap"

# --- CAMINHO DINÂMICO (Universal / GitHub Friendly) ---
# Detecta automaticamente onde o script está e aponta para a pasta de dados
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PATH_TO_DATASET = os.path.join(CURRENT_DIR, "devices/urban_observatory")

# === CENTRALIZED LIST OF URBAN OBSERVATORY DEVICES ===
# IPs: 10.0.0.50 até 10.0.0.74
URBAN_DEVICES = [
    # --- 1. AIR QUALITY (10.0.0.50 - 10.0.0.59) ---
    {"name": "gw_co",       "ip": "10.0.0.50", "var": "CO",             "topic": "city/air/co"},
    {"name": "gw_no2",      "ip": "10.0.0.51", "var": "NO2",            "topic": "city/air/no2"},
    {"name": "gw_no",       "ip": "10.0.0.52", "var": "NO",             "topic": "city/air/no"},
    {"name": "gw_nox",      "ip": "10.0.0.53", "var": "NOx",            "topic": "city/air/nox"},
    {"name": "gw_o3",       "ip": "10.0.0.54", "var": "O3",             "topic": "city/air/o3"},
    {"name": "gw_part",     "ip": "10.0.0.55", "var": "Particle",       "topic": "city/air/particle"},
    {"name": "gw_pm1",      "ip": "10.0.0.56", "var": "PM1",            "topic": "city/air/pm1"},
    {"name": "gw_pm10",     "ip": "10.0.0.57", "var": "PM10",           "topic": "city/air/pm10"},
    {"name": "gw_pm25",     "ip": "10.0.0.58", "var": "PM2.5",          "topic": "city/air/pm25"},
    {"name": "gw_pm4",      "ip": "10.0.0.59", "var": "PM 4",           "topic": "city/air/pm4"},

    # --- 2. SMART BUILDING (10.0.0.60 - 10.0.0.61) ---
    {"name": "gw_b_temp",   "ip": "10.0.0.60", "var": "Internal Temperature", "topic": "building/internal/temp"},
    {"name": "gw_b_hum",    "ip": "10.0.0.61", "var": "Internal Humidity",    "topic": "building/internal/humidity"},
    
    # --- 3. WEATHER (10.0.0.62 - 10.0.0.66) ---
    {"name": "gw_w_hum",    "ip": "10.0.0.62", "var": "Humidity",        "topic": "weather/external/humidity"},
    {"name": "gw_w_press",  "ip": "10.0.0.63", "var": "Pressure",        "topic": "weather/external/pressure"},
    {"name": "gw_w_rain",   "ip": "10.0.0.64", "var": "Rain",        "topic": "weather/external/rain"},
    {"name": "gw_w_solar",  "ip": "10.0.0.65", "var": "Solar Radiation", "topic": "weather/external/solar"},
    {"name": "gw_w_wind",   "ip": "10.0.0.66", "var": "Wind Speed",      "topic": "weather/external/wind"},
    
    # --- 4. SENSOR METRICS (10.0.0.67) ---
    {"name": "gw_m_batt",   "ip": "10.0.0.67", "var": "Battery Voltage", "topic": "metrics/battery"},

    # --- 5. WATER QUALITY (10.0.0.68 - 10.0.0.71) ---
    {"name": "gw_wq_dpt",   "ip": "10.0.0.68", "var": "Depth",              "topic": "water/quality/depth"},
    {"name": "gw_wq_do",    "ip": "10.0.0.69", "var": "Dissolved Oxygen",   "topic": "water/quality/dissolved_oxygen"},
    {"name": "gw_wq_turb",  "ip": "10.0.0.70", "var": "Turbidity",          "topic": "water/quality/turbidity"},
    {"name": "gw_wq_temp",  "ip": "10.0.0.71", "var": "Water Temperature", "topic": "water/quality/temperature"},

    # --- 6. WATER LEVEL (10.0.0.72 - 10.0.0.73) ---
    {"name": "gw_wl_abs",   "ip": "10.0.0.72", "var": "Water Level",          "topic": "water/level/absolute"},
    {"name": "gw_wl_rel",   "ip": "10.0.0.73", "var": "Relative Water Level", "topic": "water/level/relative"},
    
    # --- 7. MOBILITY (10.0.0.74) ---
    {"name": "gw_people",   "ip": "10.0.0.74", "var": "Walking",      "topic": "city/people/flow"}
]

def prepare_datasets(base_path):
    """
    Ensure that .xz files are extracted to .csv on the HOST before starting Mininet.
    This saves CPU time for the containers and prevents 'thrashing'.
    """
    info(f'*** Checking datasets in: {base_path}\n')
    
    if not os.path.exists(base_path):
        info(f'*** ERROR: Dataset path not found: {base_path}\n')
        info('*** Please check if you cloned the repo correctly.\n')
        sys.exit(1)

    # Searches for all .xz files recursively
    xz_files = glob.glob(os.path.join(base_path, "**", "*.xz"), recursive=True)
    
    # Filter only those that really need extraction
    files_to_extract = []
    for xz_file in xz_files:
        csv_file = xz_file.replace('.xz', '')
        if not os.path.exists(csv_file):
            files_to_extract.append(xz_file)
    
    if not files_to_extract:
        info('*** OK: All datasets are ready/uncompressed.\n')
        return

    # User Feedback Loop
    info(f'*** FOUND {len(files_to_extract)} COMPRESSED DATASETS.\n')
    info('*** Preparing data... This may take a few minutes (CPU intensive).\n')
    info('*** Please wait, do not close the script.\n')

    for i, xz_file in enumerate(files_to_extract, 1):
        filename = os.path.basename(xz_file)
        info(f'   [{i}/{len(files_to_extract)}] Unpacking {filename}...\n')
        try:
            # -k: keep original file, -f: force overwrite if exists (safety)
            subprocess.run(['unxz', '-k', '-f', xz_file], check=True)
        except subprocess.CalledProcessError as e:
            info(f'\n*** ERROR unpacking {filename}: {e}\n')

    info('*** Dataset preparation completed successfully.\n')
        
def stop_simulation(net, pcap_process=None):
    info('\n*** Finishing experiment...\n')
    if pcap_process:
        pcap_process.send_signal(signal.SIGINT)
        pcap_process.wait()
    if net:
        net.stop()
    os.system("docker rm -f $(docker ps -aq --filter name=mn) > /dev/null 2>&1")
    info('*** Cleaning completed.\n')
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
    
    info(f'*** Initiating IoT-Zoo Experiment \n')

    # Basic Infrastructure
    broker = net.addDocker('broker', ip=BROKER_INT_IP, dimage="myzoo/mqtt_broker", dcmd="/bin/bash")

    # Classic Devices (IPs 10.0.0.2 - 10.0.0.7)
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
    lighting_gw = net.addDocker('sl_gw', ip="10.0.0.80", dimage="myzoo/smart_lighting", 
        environment={"MQTT_BROKER_ADDR": "10.0.0.100", "MQTT_TOPIC_PUB": "city/lighting", "SLEEP_TIME": "5", "SLEEP_TIME_SD": "1"})

    # Centralized creation of urban gateways
    gateways = []
    
    for dev in URBAN_DEVICES:
        info(f'*** Gateway {dev["name"]} ({dev["ip"]}) -> Monitoring {dev["var"]}\n')
        
        gw = net.addDocker(dev["name"], ip=dev["ip"], dimage="myzoo/urban_sensor",
            volumes=[f"{PATH_TO_DATASET}:/data:ro"], 
            environment={
                "MQTT_BROKER_ADDR": BROKER_INT_IP, 
                "TIME_SCALE": "60.0",
                "TARGET_VARIABLE": dev["var"],
                "MQTT_TOPIC_PUB": dev["topic"]
            }, dcmd="/bin/bash")
        
        gateways.append(gw)

    # CCTV
    v_server = net.addDocker('v_srv', ip="10.0.0.20", dimage="myzoo/server_video", privileged=True, dcmd="/bin/bash")
    v_camera = net.addDocker('v_cam', ip="10.0.0.21", dimage="myzoo/camera",
        environment={"STREAM_SERVER_ADDR": "10.0.0.20", "STREAM_SERVER_PORT": "8554", "STREAM_NAME": "live", "VIDEO_FILE": "/video.mp4"}, privileged=True, dcmd="/bin/bash")
    v_consumer = net.addDocker('v_cons', ip="10.0.0.22", dimage="myzoo/consumer_video",
        environment={"STREAM_SERVER_ADDR": "10.0.0.20", "STREAM_SERVER_PORT": "8554", "STREAM_NAME": "live", "ACTIVE_TIME": str(args.time)}, privileged=True, dcmd="/bin/bash")

    s1 = net.addSwitch('s1')
    
    # Consolidate all nodes
    all_nodes = [broker, predio, cooler, domotic, predictive, air, patient1, lighting_gw, v_server, v_camera, v_consumer] + gateways
    
    for node in all_nodes:
        net.addLink(node, s1)
    
    nat = net.addNAT(name='nat0', ip='10.0.0.254')
    net.addLink(nat, s1)

    info('*** Starting Network...\n')
    net.start()

    for node in all_nodes:
        node.cmd('ip route del default 2> /dev/null') 
        node.cmd('ip route add default via 10.0.0.254')
        fix_checksum(node)
    fix_checksum(nat)

    info(f'*** Starting tcpdump...\n')
    s1.cmd(f"tcpdump -i any -w {pcap_path} -U not port 6653 &")

    info('*** Starting Services...\n')
    broker.cmd('/usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf -d &')
    
    # Network Fix for Ubuntu/Privileged containers
    v_server.cmd('ip link set v_srv-eth0 up')
    v_camera.cmd('ip link set v_cam-eth0 up')
    v_consumer.cmd('ip link set v_cons-eth0 up')
    time.sleep(1)
    
    v_server.cmd('/mediamtx /mediamtx.yml > /tmp/v_srv.log 2>&1 &')
    time.sleep(3) # Wait for the server to boot up before turning on the camera.

    predio.cmd('python3 -u /client.py > /dev/null 2>&1 &')
    cooler.cmd('python3 -u /client.py > /dev/null 2>&1 &')
    domotic.cmd('python3 -u /client_bis.py > /dev/null 2>&1 &') 
    predictive.cmd('python3 -u /client.py > /dev/null 2>&1 &')
    air.cmd('python3 -u /client.py > /dev/null 2>&1 &')
    patient1.cmd('python3 -u /client.py > /dev/null 2>&1 &')
    lighting_gw.cmd('python3 -u /client.py > /tmp/sl_gw.log 2>&1 &')
    
    v_camera.cmd('python3 -u /ip_camera.py > /tmp/v_cam.log 2>&1 &')
    v_consumer.cmd('python3 -u /consume.py > /tmp/v_cons.log 2>&1 &')
    
    for gw in gateways:
        gw.cmd(f'python3 -u /urban_sensor.py > /tmp/{gw.name}.log 2>&1 &')

    info(f'*** Running simulation by {args.time}s...\n')
    try:
        start_time = time.time()
        while (time.time() - start_time) < args.time:
            remaining = int(args.time - (time.time() - start_time))
            sys.stdout.write(f"\rTime remaining: {remaining}s    ")
            sys.stdout.flush()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        stop_simulation(net, None)

if __name__ == '__main__':
    # Uses the dynamic path detected at the top of the script
    prepare_datasets(PATH_TO_DATASET)
    run()
