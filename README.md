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


## 📋 Prerequisites

To ensure faithful experiment reproduction, make sure you meet the following requirements:

* 🐧 **Operating System:** Ubuntu 20.04 LTS or 22.04 LTS (Virtual Machine or Bare Metal).
* 💻 **Recommended Hardware:** Minimum 8GB RAM and 2 vCPUs
* 💾 **Storage:** At least 50 GB of available disk space (SSD recommended).
* 🔑 **Permissions:** `root` access (`sudo`) is required for Mininet to manage network interfaces.
---

## 🚀 Installation Guide (Step by Step)

### 1. System Preparation (Containernet)

This project uses Containernet, an extension of Mininet that allows Docker containers to be used as hosts in the topology.

```bash
# 1. Update the system and install essential tools
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git ansible python3-pip

# 2. Install Containernet (via Ansible - Recommended Method)
git clone https://github.com/containernet/containernet.git
cd containernet/ansible
sudo ansible-playbook -i "localhost," -c local install.yml
cd ..
sudo make install

# 3. Install Python dependencies for the orchestrator
sudo pip3 install docker pandas scikit-learn
```

### 2. IoT-Zoo Project Setup

Clone this repository to your local machine:

```bash
cd ~
git clone https://github.com/GT-IoTEdu/Testbed-Virtual-02.git
cd Testbed-Virtual-02
```

### 3. Environment Build

There is no need to manually configure certificates or containers. The script build_images.sh automates the entire process:

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

### Syntax

```bash
sudo python3 run_experiment.py --time <seconds> --output <path_to_file.pcap>
```

### Usage Examples (Recommended)

⚠️ **Note:** To avoid system permission blocks (AppArmor) when writing capture files, we recommend saving the output in `/tmp`.

**Quick Test — generate the PCAP file (120 seconds):**
```bash
sudo python3 run_experiment.py --time 120 --output /tmp/iot_zoo_test.pcap
```

**After the experiment finishes, move the generated file to the project directory:**
```bash
sudo mv /tmp/iot_zoo_test.pcap ./iot_zoo_test.pcap
sudo chown $USER:$USER ./iot_zoo_test.pcap
```

**Full Dataset — generate the PCAP file (10 minutes):**
```bash
sudo python3 run_experiment.py --time 600 --output /tmp/iot_zoo_full.pcap
```

**After the experiment finishes, move the generated file to the project directory:**
```bash
sudo mv /tmp/iot_zoo_full.pcap ./iot_zoo_full.pcap
sudo chown $USER:$USER ./iot_zoo_full.pcap
```

---

## 🔍 Analyzing the Results

Open the generated `.pcap` file in **Wireshark** to validate the traffic:

1.  **MQTT Filter (`tcp.port == 1883`):**
    * Observe the diversity of topics: `hospital/patients`, `vibration/cooler`, etc.
    * Note the different payload formats (JSON, Binary, XML).

2.  **Video Filter (`udp` ou `rtsp`):**
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
| **Infrastructure** | **MQTT Broker** | `broker` (`10.0.0.100`) | Central Mosquitto server managing all message traffic. |
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
The experiment uses a star topology managed by Mininet, where all devices communicate through a virtual switch (`s1`). The network is anchored by a **Central MQTT Broker** (`10.0.0.100`) for data messaging and a **Video Server** (`10.0.0.20`) for multimedia streaming, with an internet exit node via NAT (`10.0.0.254`).

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
