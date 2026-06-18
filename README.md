# 🛡️ IoT-Zoo Testbed: Heterogeneous Simulation Environment

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/platform-linux--sudo-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

This repository contains the implementation of a **reproducible IoT testbed** based on **Mininet / Containernet**. The project simulates an "IoT Zoo" featuring heterogeneous devices, from medical and industrial sensors to surveillance cameras and weather stations, all running simultaneously in Docker containers.

> **Goal:** Generate realistic network traffic and labeled datasets for training and validating **Intrusion Detection Systems (IDS)** in IoT/IIoT scenarios.

---

## Considered Badges
- Available Artifacts (Badge D)
- Functional Artifacts (Badge F)
- Sustainable Artifacts (Badge S)
- Reproducible Experiments (Badge R)

## Directory Structure
* `devices/`: Source code and `Dockerfiles` for each implemented device.
* `devices/certificates/`: (Generated during build) CA and TLS certificates.
* `build_images.sh`: Main automation script for environment setup.
* `run_experiment.py`: Python/Mininet orchestrator for topology and capture.
* `convert_PCAP_to_csv/`: Tools to transform raw traffic (PCAP) into enriched ML-ready datasets (i.e., .csv with 17 features).
* `ARCHITECTURE.md`: Provides an overview of the IoT-Zoo architecture, describing how the build, orchestration, emulation and data collection layers interact.
* `DEVICE_PROFILES.md`: Explains how device profiles are structured, how they are configured through environment variables, how they interact with `run_experiment.py`, and how new profiles can be integrated into the testbed.


## 📋 Prerequisites

To ensure faithful experiment reproduction, make sure you meet the following requirements:

* 🐧 **Operating System:** Ubuntu 20.04 LTS or 22.04 LTS (Virtual Machine or Bare Metal).
* 💻 **Recommended Hardware:** Minimum 8GB RAM and 2 vCPUs
* 💾 **Storage:** At least 50 GB of available disk space (SSD recommended).
* 🔑 **Permissions:** `root` access (`sudo`) is required for Mininet to manage network interfaces.
* 🐳 **Docker:** Installed automatically by the Containernet installation script when needed.
---

## Security Concerns

This artifact does not execute attacks against external hosts, real IoT devices, production networks, or cloud services. All generated traffic is confined to the local Mininet/Containernet emulated topology.

The main security consideration is that the experiment requires `sudo` privileges because Mininet/Containernet needs to create virtual interfaces, namespaces, links, Docker containers and packet capture processes. For this reason, we recommend running the artifact inside a dedicated virtual machine.

---

## 🚀 Installation Guide (Step by Step)

### 1. System Preparation

Update the system and install the required base packages:
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git ansible python3-pip iptables python3-iptables
```
Install Python dependencies used by the experiment orchestrator and data processing tools:
```bash
sudo pip3 install docker pandas scikit-learn
```

### 2. Install Containernet
This project uses Containernet, an extension of Mininet that allows Docker containers to be used as hosts in the emulated topology.
Before installing, remove possible leftovers from previous Mininet/Containernet installations:
```bash
cd ~
sudo rm -rf containernet
sudo rm -rf openflow
sudo rm -rf oflops
sudo rm -rf pox
sudo rm -rf openvswitch
```
Clone and install Containernet:
```bash
cd ~
git clone https://github.com/containernet/containernet.git
cd containernet/ansible
sudo ansible-playbook -i "localhost," -c local install.yml
```
The Ansible installation should finish with `failed=0`.
Then run:
```bash
cd ~/containernet
sudo make install
```
---
### 3. Validate Containernet / Mininet
First, test whether Python can import Mininet from inside the Containernet directory:
```bash
cd ~/containernet
python3 -c "import mininet; print('mininet OK')"
sudo python3 -c "from mininet.net import Containernet; print('Containernet OK')"
```
Expected output:
```bash
mininet OK
Containernet OK
```
Then test the same import from the IoT-Zoo project directory after cloning the repository in the next step. If the module is not found outside `~/containernet`, use the `PYTHONPATH` execution form shown in the experiment section.

---


### 4. IoT-Zoo Project Setup

Clone this repository to your local machine:
```bash
cd ~
git clone https://github.com/GT-IoTEdu/Testbed-Virtual-02.git
cd Testbed-Virtual-02
```
Check whether Containernet is available from the project directory:
```bash
sudo python3 -c "from mininet.net import Containernet; print('Containernet OK')"
```
If this command works, the experiment can be executed with `sudo python3`.
If it does not work, use the `PYTHONPATH` form below, which explicitly informs Python where Containernet is located:
```bash
sudo PYTHONPATH=/home/$USER/containernet python3 -c "from mininet.net import Containernet; print('Containernet OK')"
```
Expected output:
```bash
Containernet OK
```


### 5. Environment Build

There is no need to manually configure certificates or containers. The script `build_images.sh` automates the environment build:

1.  Sets execution permissions.
2.  Generates a simulated **PKI** (Public Key Infrastructure) for TLS.
3.  Builds the **Docker images** for each sensor.

```bash
# Ensure execution permission
chmod +x build_images.sh

# Start the build (May take a few minutes the first time)
sudo ./build_images.sh
```

> ✅ **Success:** Wait until you see: 🎉 SUCCESS! The environment is ready.

---

## ▶️ Running the Experiment

The script `run_experiment.py` is the main orchestrator. It brings up the topology, configures routing, and starts traffic capture.

### Syntax (Recommended Execution)

To make the experiment independent from Python path differences across installations, use the following form:
```bash
sudo PYTHONPATH=/home/$USER/containernet python3 run_experiment.py --time <seconds> --output <path_to_file.pcap>
```

### Usage Examples (Recommended)

⚠️ **Note:** To avoid system permission blocks (AppArmor) when writing capture files, we recommend saving the output in `/tmp`.

**Quick Test — generate the PCAP file (120 seconds):**
```bash
cd ~/Testbed-Virtual-02
sudo PYTHONPATH=/home/$USER/containernet python3 run_experiment.py --time 120 --output /tmp/iot_zoo_test.pcap
```
After the experiment finishes, move the generated file to the project directory:
```bash
sudo mv /tmp/iot_zoo_test.pcap ./iot_zoo_test.pcap
sudo chown $USER:$USER ./iot_zoo_test.pcap
```


**After the experiment finishes, move the generated file to the project directory:**
```bash
sudo mv /tmp/iot_zoo_test.pcap ./iot_zoo_test.pcap
sudo chown $USER:$USER ./iot_zoo_test.pcap
```

**Full Dataset — generate the PCAP file (10 minutes):**
```bash
cd ~/Testbed-Virtual-02
sudo PYTHONPATH=/home/$USER/containernet python3 run_experiment.py --time 600 --output /tmp/iot_zoo_full.pcap
```
After the experiment finishes, move the generated file to the project directory:
```bash
sudo mv /tmp/iot_zoo_full.pcap ./iot_zoo_full.pcap
sudo chown $USER:$USER ./iot_zoo_full.pcap
```
> ⚠️ **Note:** Saving the `.pcap` file in `/tmp` is recommended to avoid permission blocks when packet capture tools write files directly inside the user's home directory.

### Selecting the telemetry protocol (MQTT / Zenoh / DDS-XRCE)

The testbed supports three IoT telemetry protocols over the **same star topology**.
The protocol is chosen with the `PROTOCOL` environment variable (default `mqtt`).
Each run starts only the corresponding central node and launches the matching
client on every device, so you can generate a separate `.pcap` per protocol:

```bash
# MQTT (default) — Mosquitto broker (10.0.0.100), port 1883
sudo PYTHONPATH=/home/$USER/containernet python3 run_experiment.py -t 120 -o /tmp/mqtt.pcap

# Zenoh — Eclipse Zenoh router (10.0.0.101), port 7447
sudo PROTOCOL=zenoh PYTHONPATH=/home/$USER/containernet python3 run_experiment.py -t 120 -o /tmp/zenoh.pcap

# DDS-XRCE — eProsima Micro-XRCE-DDS agent (10.0.0.102), UDP 8888
sudo PROTOCOL=xrce PYTHONPATH=/home/$USER/containernet python3 run_experiment.py -t 120 -o /tmp/xrce.pcap
```

- **MQTT**: each device runs its original `client.py` (paho-mqtt).
- **Zenoh**: each device runs `client_zenoh.py` — a faithful copy of `client.py` with
  only the connection layer swapped through the `iotzoo_zenoh` shim
  (`devices/_zenoh_common/`). Full parity across all telemetry devices.
- **DDS-XRCE**: a single generic C publisher (`devices/_xrce_common/`, image
  `myzoo/xrce_client_base`) reused by every device, fed by the device's dataset and
  publishing to the agent. The urban-observatory pandas pipeline is covered by
  MQTT/Zenoh only.

### Compatibility notes (Linux)

- **Line endings:** all scripts must keep **LF** endings. A CRLF in a shebang
  (e.g. `#!/usr/bin/env python3\r`) makes the kernel look for an interpreter
  `python3\r` and the device entrypoint fails to start on Linux. A `.gitattributes`
  enforces LF for `*.py`/`*.sh`/`*.c`; do not commit CRLF.
- **Zenoh version is pinned to `1.5.0`** (router image and `eclipse-zenoh` Python
  wheel) because the device images are built on `ubuntu:focal` (Python 3.8), and
  `1.5.0` is the last release shipping a `cp38` wheel — `1.6+` only provide a Rust
  source distribution that fails to build on focal. Bumping it requires a newer
  Python base image. Router and client must stay on the same 1.x line.

### Quick standalone smoke test (no Containernet)

To verify a single protocol end-to-end without the full topology (useful on a dev
box without Containernet), use a Docker bridge network. Example for Zenoh:

```bash
docker network create iotzoo_test
docker run -d --name zr --network iotzoo_test myzoo/zenoh_router -c "zenohd"
# subscriber:
docker run --rm --network iotzoo_test --entrypoint python3 myzoo/building_monitor -u -c \
  'import zenoh,time;c=zenoh.Config();c.insert_json5("mode","\"client\"");c.insert_json5("connect/endpoints","[\"tcp/zr:7447\"]");s=zenoh.open(c);s.declare_subscriber("building/**",lambda k:print(k.key_expr,k.payload.to_bytes().decode()));time.sleep(30)' &
# device in zenoh mode (override the ENTRYPOINT, which defaults to the MQTT client.py):
docker run --rm --network iotzoo_test -e MQTT_BROKER_ADDR=zr -e MQTT_TOPIC_PUB=building -e SLEEP_TIME=2 \
  --entrypoint python3 myzoo/building_monitor -u /client_zenoh.py
```

For DDS-XRCE the C publisher needs the agent's **IPv4 address** (not a hostname):
`MicroXRCEAgent udp4 -p 8888` on the agent, then
`client_xrce <AGENT_IP> 8888 building /dataset.csv 2` on `myzoo/xrce_client_base`
with a plain-CSV dataset mounted at `/dataset.csv`.

---


**Optional: Create a Shortcut Command**
To avoid typing the full `PYTHONPATH` command every time, create an alias:
```bash
echo 'alias run-iot-zoo="cd ~/Testbed-Virtual-02 && sudo PYTHONPATH=/home/$USER/containernet python3 run_experiment.py"' >> ~/.bashrc
source ~/.bashrc
```
Then run:
```bash
run-iot-zoo --time 120 --output /tmp/iot_zoo_test.pcap
```

---

## 🔍 Analyzing the Results

Open the generated `.pcap` file in **Wireshark** to validate the traffic:

1.  **MQTT Filter (`tcp.port == 1883`):**
    * Observe the diversity of topics: `hospital/patients`, `vibration/cooler`, etc.
    * Note the different payload formats (JSON, Binary, XML).

2.  **Zenoh Filter (`tcp.port == 7447`):**
    * Present when running with `PROTOCOL=zenoh`; traffic between devices and the Zenoh router (`10.0.0.101`).

3.  **DDS-XRCE Filter (`udp.port == 8888`):**
    * Present when running with `PROTOCOL=xrce`; client↔agent traffic to the DDS-XRCE agent (`10.0.0.102`).

4.  **Video Filter (`udp` ou `rtsp`):**
    * Verify the continuous flow of UDP packets between the Camera (`.21`) and the Server (`.20`).

---

## 📊 Data Extraction (ML Readiness)

Once you have generated a `.pcap` file, you can use the automated converter to generate an enriched CSV dataset with **17 features**, including deep packet inspection for MQTT and network layer metrics.

### Prerequisites for Extraction
If you intend to generate CSV datasets, you must install Tshark and the required Python libraries on your host:

```bash
# Install Tshark (Wireshark CLI)
sudo apt-get update && sudo apt-get install -y tshark

# Install extraction dependencies
pip3 install pandas scapy
```

### Automated Conversion
Navigate to the converter directory and run the orchestrator:

```bash
cd convert_PCAP_to_csv/
python3 main.py --input ../meu_dataset.pcap --output final_zoo_dataset.csv
```

### Automated Conversion
The resulting dataset includes:
*  Network Metrics: IP TTL, TCP Sequence numbers, and TCP Flags.
*  IoT Context: Full MQTT dissection (Topic, Message Type, QoS, and Payload Length).
*  Protocol Diversity: Identification of RTSP, DNS, NTP, and MQTT across all 43 device profiles.

* 📁 For more details on the extraction process and feature definitions, see the [Converter README](convert_pcap_to_csv/README.md).

---

## 🏛️ Scenario Architecture (IoT Zoo)

The environment simulates a heterogeneous network where distinct IoT domains coexist, ranging from legacy industrial sensors to high-frequency urban monitoring systems using real-world datasets.

### 📋 Device List

| Domain | Function | Device (`IP`) | Description |
| :--- | :--- | :--- | :--- |
| **Infrastructure** | **MQTT Broker** | `broker` (`10.0.0.100`) | Central Mosquitto server (`PROTOCOL=mqtt`). |
| **Infrastructure** | **Zenoh Router** | `zenoh` (`10.0.0.101`) | Eclipse Zenoh router (`PROTOCOL=zenoh`, port 7447). |
| **Infrastructure** | **DDS-XRCE Agent** | `xrce` (`10.0.0.102`) | eProsima Micro-XRCE-DDS agent (`PROTOCOL=xrce`, UDP 8888). |
| **Infrastructure** | **Media Server** | `v_server` (`10.0.0.20`) | RTSP Server (MediaMTX) distributing video streams. |
| **Infrastructure** | **NAT Gateway** | `nat0` (`10.0.0.254`) | Network Address Translation interface for internet access. |
| **e-Health** | **IoMT (ECG)** | `patient1` (`10.0.0.7`) | Simulates vital signs with high-frequency MQTT (JSON). Includes time drift simulation. |
| **Industry 4.0** | **Vibration Sensor** | `cooler` (`10.0.0.3`) | Industrial motor monitor. Sends raw binary payloads in **Base64**. |
| **Industry 4.0** | **Telemetry** | `predictive` (`10.0.0.5`) | Predictive maintenance sensor monitoring machine status (JSON). |
| **Smart Building** | **Management** | `predio` (`10.0.0.2`) | General occupancy and lighting sensors (JSON). |
| **Smart Home** | **Automation** | `domotic` (`10.0.0.4`) | Residential automation using legacy **XML** format. |
| **Smart City** | **Base Station** | `air` (`10.0.0.6`) | Air quality station (**XML**). |
| **Smart City** | **Smart Lighting** | `sl_gw` (`10.0.0.80`) | Monitors energy consumption (kWh), ambient light (Lux), and control actions for fault detection. |
| **CCTV** | **IP Camera** | `v_camera` (`10.0.0.21`) | Transmits real video stream (H.264) via FFmpeg (RTSP/UDP). |
| **CCTV** | **DVR Client** | `v_consumer` (`10.0.0.22`) | Consumer node that subscribes to and records the RTSP stream. |
| **Air Quality** | **Carbon Monoxide** | `gw_co` (`10.0.0.50`) | Real data from Urban Observatory (Newcastle). |
| **Air Quality** | **Nitrogen Dioxide** | `gw_no2` (`10.0.0.51`) | Real data from Urban Observatory. |
| **Air Quality** | **Nitric Oxide** | `gw_no` (`10.0.0.52`) | Real data from Urban Observatory. |
| **Air Quality** | **Nitrogen Oxides** | `gw_nox` (`10.0.0.53`) | Real data from Urban Observatory. |
| **Air Quality** | **Ozone** | `gw_o3` (`10.0.0.54`) | Real data from Urban Observatory. |
| **Air Quality** | **Particle Count** | `gw_part` (`10.0.0.55`) | Real data from Urban Observatory. |
| **Air Quality** | **PM 1.0** | `gw_pm1` (`10.0.0.56`) | Particulate Matter ≤ 1µm. Real data from Urban Observatory. |
| **Air Quality** | **PM 10** | `gw_pm10` (`10.0.0.57`) | Particulate Matter ≤ 10µm. Real data from Urban Observatory. |
| **Air Quality** | **PM 2.5** | `gw_pm25` (`10.0.0.58`) | Particulate Matter ≤ 2.5µm. Real data from Urban Observatory. |
| **Air Quality** | **PM 4.0** | `gw_pm4` (`10.0.0.59`) | Particulate Matter ≤ 4µm. Real data from Urban Observatory. |
| **Smart Building** | **Int. Temperature** | `gw_b_temp` (`10.0.0.60`) | Real data from Urban Observatory. |
| **Smart Building** | **Int. Humidity** | `gw_b_hum` (`10.0.0.61`) | Real data from Urban Observatory. |
| **Weather** | **Ext. Humidity** | `gw_w_hum` (`10.0.0.62`) | Real data from Urban Observatory. |
| **Weather** | **Pressure** | `gw_w_press` (`10.0.0.63`) | Real data from Urban Observatory. |
| **Weather** | **Rainfall** | `gw_w_rain` (`10.0.0.64`) | Real data from Urban Observatory. |
| **Weather** | **Solar Radiation** | `gw_w_solar` (`10.0.0.65`) | Real data from Urban Observatory. |
| **Weather** | **Wind Speed** | `gw_w_wind` (`10.0.0.66`) | Real data from Urban Observatory. |
| **Metrics** | **Battery Voltage** | `gw_m_batt` (`10.0.0.67`) | IoT device battery levels. Real data from Urban Observatory. |
| **Water Quality** | **Depth** | `gw_wq_dpt` (`10.0.0.68`) | Real data from Water Observatory. |
| **Water Quality** | **Dissolved Oxygen**| `gw_wq_do` (`10.0.0.69`) | Real data from Water Observatory. |
| **Water Quality** | **Turbidity** | `gw_wq_turb` (`10.0.0.70`) | Real data from Water Observatory. |
| **Water Quality** | **Temperature** | `gw_wq_temp` (`10.0.0.71`) | Real data from Water Observatory. |
| **Water Level** | **Absolute Level** | `gw_wl_abs` (`10.0.0.72`) | Real data from Urban Observatory. |
| **Water Level** | **Relative Level** | `gw_wl_rel` (`10.0.0.73`) | Real data from Urban Observatory. |
| **Mobility** | **Pedestrian Count**| `gw_people` (`10.0.0.74`) | Footfall/Walking data from People Counter sensors. |

### 🔗 Network Topology
The experiment uses a star topology managed by Mininet, where all devices communicate through a virtual switch (`s1`). The network is anchored by three protocol infrastructure nodes — a **Central MQTT Broker** (`10.0.0.100`), a **Zenoh Router** (`10.0.0.101`), and a **DDS-XRCE Agent** (`10.0.0.102`) — plus a **Video Server** (`10.0.0.20`) for multimedia streaming, with an internet exit node via NAT (`10.0.0.254`). The active telemetry protocol is selected with the `PROTOCOL` variable (see *Selecting the telemetry protocol*).

---

## ❓ Common Troubleshooting

<details>
<summary><strong>Click to view error fixes</strong></summary>

### Error: `tcpdump: permission denied` or 0-byte capture file
* **Cause:** Ubuntu AppArmor blocks tcpdump from writing to the `/home` directory.
* **Fix:** Save output to `/tmp/` (e.g., `--output /tmp/teste.pcap`) and then move the file.

### Erro: `RTNETLINK answers: File exists`
* **Cause:** A previous run was abruptly interrupted and left virtual interfaces behind.
* **Fix:** Run the command below to clean Mininet:
    ```bash
    sudo mn -c
    ```
</details>



## 📜 License and Citation

***Copyright (c) [2026] [RNP – REDE NACIONAL DE ENSINO E PESQUISA]***

Este código foi desenvolvido pelo GT-IoTEdu e está licenciado sob os termos da Licença BSD. Ele pode ser livremente utilizado, modificado e distribuído, inclusive para fins comerciais, desde que este aviso de direitos autorais seja mantido.

Este software é fornecido “como está”, sem qualquer garantia, expressa ou implícita, incluindo, sem limitação, garantias de comercialização ou adequação a um propósito específico. A RNP e os autores não se responsabilizam por quaisquer danos ou prejuízos decorrentes do uso deste software.

If you use it in your research, please cite:
> Quincozes, V., Kreutz, D., & Ereno Quincozes, S. (2026). IoT-Zoo Network Traffic (1.1.0) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.19389681.
