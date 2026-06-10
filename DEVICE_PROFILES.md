# Device Profiles

IoT-Zoo models each IoT device as a **containerized device profile**. A profile represents a specific IoT behavior, including its dataset, runtime logic, protocol behavior, payload format, timing pattern and network configuration.

This document describes how device profiles are organized, how they interact with the experiment orchestrator and how new profiles can be added to the testbed.

---

## 1. Profile-based organization

All device profiles are stored under:

```bash
devices/
```

Each subdirectory represents either an infrastructure service or an IoT device profile.

Example:

```bash
devices/
├── air_quality/
├── aquaponics_fish_pond/
├── building_monitor/
├── cooler_motor/
├── domotic_monitor/
├── environmental_sensors/
├── farming_sensor/
├── greenhouse_sensor/
├── ip_camera/
├── mhealth-device/
├── mqtt_broker/
├── predictive_maintenance/
├── smart_lighting/
├── stream_consumer/
├── stream_server/
└── urban_observatory/
```

A typical device profile contains:

```bash
devices/<profile_name>/
├── Dockerfile
├── client.py
└── dataset file(s)
```

Depending on the profile, the runtime script may use another name, such as:

```bash
client.py
client_bis.py
urban_sensor.py
ip_camera.py
consume.py
```

---

## 2. What is a device profile?

A device profile is a self-contained unit responsible for generating realistic application traffic.

Each profile usually defines:

1. **Execution environment**
   Defined in the `Dockerfile`.

2. **Data source**
   A dataset file, video file, compressed dataset or synthetic data source.

3. **Runtime behavior**
   Implemented in a Python script such as `client.py`.

4. **Protocol behavior**
   Usually MQTT for telemetry or RTSP/UDP for video streams.

5. **Payload format**
   JSON, XML, binary, plain text or protocol-specific payloads.

6. **Timing behavior**
   Transmission interval, jitter, active/inactive periods or dataset-driven replay speed.

7. **Network configuration**
   IP address, MQTT topic, broker address and optional service-specific parameters.

---

## 3. Main profile components

### 3.1 `Dockerfile`

The `Dockerfile` defines the container environment for the profile.

It usually performs the following tasks:

* selects a base image;
* installs Linux packages;
* installs Python dependencies;
* copies datasets into the container;
* copies runtime scripts into the container;
* defines the entrypoint or default command.

Example structure:

```dockerfile
FROM ubuntu:focal

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    iputils-ping \
    iproute2 \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir paho-mqtt==1.6.1

COPY dataset.csv /dataset.csv
COPY client.py /client.py

RUN chmod +x /client.py

ENTRYPOINT ["/client.py"]
```

---

### 3.2 Runtime script

The runtime script defines how the device behaves during the experiment.

For MQTT-based profiles, the runtime script usually:

* reads a dataset or generates telemetry;
* transforms each record into an application payload;
* connects to the MQTT broker;
* publishes messages to a specific topic;
* controls the transmission interval;
* handles termination signals.

For video profiles, the runtime script may:

* start an RTSP stream;
* transmit video data;
* consume a video stream;
* write service logs.

---

### 3.3 Dataset files

A profile may include one or more dataset files. These files can be stored directly inside the profile directory or copied into the image during the Docker build.

Examples of dataset formats include:

```bash
.csv
.csv.xz
.json
.txt
.mp4
```

Compressed datasets can be unpacked before or during experiment execution, depending on the profile design.

---

## 4. Runtime configuration with environment variables

Most profiles receive configuration from `run_experiment.py` through Docker environment variables.

Common variables include:

| Variable           | Description                                              |
| ------------------ | -------------------------------------------------------- |
| `MQTT_BROKER_ADDR` | IP address of the MQTT broker used by the profile.       |
| `MQTT_TOPIC_PUB`   | MQTT topic used for publishing telemetry.                |
| `MQTT_QOS`         | MQTT quality of service level.                           |
| `SLEEP_TIME`       | Average interval between transmissions.                  |
| `SLEEP_TIME_SD`    | Standard deviation applied to the transmission interval. |
| `ACTIVE_TIME`      | Duration of the active transmission period.              |
| `INACTIVE_TIME`    | Duration of inactive/sleep period, when supported.       |
| `TLS`              | Enables TLS communication, when supported.               |
| `TLS_INSECURE`     | Disables hostname verification when TLS is enabled.      |

Profile-specific variables may also be used. For example, urban observatory profiles may use variables such as:

| Variable          | Description                                                 |
| ----------------- | ----------------------------------------------------------- |
| `TARGET_VARIABLE` | Selects which variable from the dataset should be replayed. |
| `TIME_SCALE`      | Controls the replay speed of dataset-driven telemetry.      |

Video profiles may use variables such as:

| Variable             | Description                            |
| -------------------- | -------------------------------------- |
| `STREAM_SERVER_ADDR` | IP address of the RTSP server.         |
| `STREAM_SERVER_PORT` | RTSP server port.                      |
| `STREAM_NAME`        | Name of the video stream.              |
| `VIDEO_FILE`         | Video file used by the camera profile. |

---

## 5. Example: Air Quality profile

The `air_quality` profile is an example of a dataset-driven MQTT device profile.

Typical files:

```bash
devices/air_quality/
├── Dockerfile
├── client.py
└── air_quality/
    └── AirQualityUCI.csv.xz
```

### 5.1 Docker image

The Dockerfile prepares the runtime environment by:

* using Ubuntu as base image;
* installing networking tools;
* installing Python 3 and `pip`;
* installing the MQTT client dependency;
* copying the compressed air quality dataset into the container;
* copying the Python client;
* setting the client as the entrypoint.

### 5.2 Runtime behavior

The runtime script:

* opens the compressed dataset;
* reads the dataset line by line;
* loops back to the beginning when the end of the file is reached;
* converts each row into a structured payload;
* builds an XML representation of the telemetry record;
* publishes the payload to the MQTT broker;
* periodically pings the broker;
* optionally polls an NTP server;
* controls active and inactive telemetry periods.

This profile demonstrates the general IoT-Zoo pattern: a dataset is transformed into application-level traffic and transmitted through a real protocol.

---

## 6. Interaction with `run_experiment.py`

The file `run_experiment.py` is responsible for adding each profile to the Containernet topology.

A typical MQTT profile is added with:

```python
air = net.addDocker(
    'air',
    ip="10.0.0.6",
    dimage="myzoo/air_quality",
    environment={
        "MQTT_BROKER_ADDR": BROKER_INT_IP,
        "SLEEP_TIME": "5"
    },
    dcmd="/bin/bash"
)
```

After the node is created, it must be connected to the virtual switch:

```python
net.addLink(air, s1)
```

During service startup, the profile client is executed inside the container:

```python
air.cmd('python3 -u /client.py > /dev/null 2>&1 &')
```

---

## 7. Infrastructure profiles

Some directories under `devices/` are not IoT sensors, but infrastructure services required by the experiment.

Examples:

| Directory          | Role                                                              |
| ------------------ | ----------------------------------------------------------------- |
| `mqtt_broker/`     | Provides the Mosquitto MQTT broker.                               |
| `stream_server/`   | Provides the RTSP/video streaming server.                         |
| `stream_consumer/` | Consumes the RTSP stream.                                         |
| `ip_camera/`       | Produces the video stream.                                        |
| `certificates/`    | Stores or generates TLS/PKI artifacts used by supported profiles. |

These profiles are part of the emulation environment and support communication among IoT devices.

---

## 8. Urban Observatory profiles

The `urban_observatory` profile is used to instantiate multiple smart-city gateways from a common Docker image and dataset source.

Instead of creating a separate Docker image for each urban variable, `run_experiment.py` defines a centralized list of devices with:

* container name;
* IP address;
* target variable;
* MQTT topic.

Example pattern:

```python
URBAN_DEVICES = [
    {"name": "gw_co", "ip": "10.0.0.50", "var": "CO", "topic": "city/air/co"},
    {"name": "gw_no2", "ip": "10.0.0.51", "var": "NO2", "topic": "city/air/no2"},
]
```

Each gateway is instantiated from the same image:

```python
gw = net.addDocker(
    dev["name"],
    ip=dev["ip"],
    dimage="myzoo/urban_sensor",
    volumes=[f"{PATH_TO_DATASET}:/data:ro"],
    environment={
        "MQTT_BROKER_ADDR": BROKER_INT_IP,
        "TIME_SCALE": "60.0",
        "TARGET_VARIABLE": dev["var"],
        "MQTT_TOPIC_PUB": dev["topic"]
    },
    dcmd="/bin/bash"
)
```

This design avoids duplicated code and allows multiple smart-city profiles to share a common implementation while producing different telemetry streams.

---

## 9. Adding a new device profile

To add a new profile, follow the steps below.

### Step 1: Create a new profile directory

```bash
mkdir -p devices/my_new_sensor
```

Recommended structure:

```bash
devices/my_new_sensor/
├── Dockerfile
├── client.py
└── dataset.csv
```

---

### Step 2: Create the Dockerfile

Example:

```dockerfile
FROM ubuntu:focal

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    iputils-ping \
    iproute2 \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir paho-mqtt==1.6.1

COPY dataset.csv /dataset.csv
COPY client.py /client.py

RUN chmod +x /client.py

ENTRYPOINT ["/client.py"]
```

---

### Step 3: Implement the runtime script

The runtime script should define how the dataset is transformed into traffic.

For an MQTT-based profile, the script should usually:

1. read the dataset;
2. select or transform relevant columns;
3. build a payload;
4. publish to the MQTT broker;
5. wait for the next transmission interval;
6. stop gracefully when the experiment ends.

Recommended environment variables:

```bash
MQTT_BROKER_ADDR
MQTT_TOPIC_PUB
SLEEP_TIME
SLEEP_TIME_SD
```

---

### Step 4: Add the image to `scripts/build_images.sh`

Add a Docker build command for the new profile:

```bash
docker build -t myzoo/my_new_sensor ./devices/my_new_sensor
```

---

### Step 5: Add the container to `run_experiment.py`

Create the container:

```python
my_new_sensor = net.addDocker(
    'my_sensor',
    ip="10.0.0.30",
    dimage="myzoo/my_new_sensor",
    environment={
        "MQTT_BROKER_ADDR": BROKER_INT_IP,
        "MQTT_TOPIC_PUB": "my/sensor/topic",
        "SLEEP_TIME": "5",
        "SLEEP_TIME_SD": "1"
    },
    dcmd="/bin/bash"
)
```

Add it to the list of nodes:

```python
all_nodes = [..., my_new_sensor]
```

Start the client:

```python
my_new_sensor.cmd('python3 -u /client.py > /tmp/my_sensor.log 2>&1 &')
```

---

### Step 6: Rebuild the images

```bash
./scripts/build_images.sh --full
```

---

### Step 7: Run the experiment

```bash
./scripts/run_full.sh --time 120 --output /tmp/iot_zoo_test.pcap
```

---

### Step 8: Validate the generated traffic

Open the generated PCAP file in Wireshark and filter MQTT traffic:

```text
tcp.port == 1883
```

Check whether the new MQTT topic appears:

```text
my/sensor/topic
```

You can also inspect MQTT traffic from the terminal:

```bash
tcpdump -r /tmp/iot_zoo_test.pcap -n port 1883 -c 10
```

---

## 10. Profile development checklist

Before submitting or merging a new profile, check:

* [ ] The profile has its own directory under `devices/`.
* [ ] The profile includes a `Dockerfile`.
* [ ] The profile includes a runtime script.
* [ ] The dataset source is included or clearly documented.
* [ ] Required Python packages are installed in the Dockerfile.
* [ ] MQTT topic or protocol endpoint is defined.
* [ ] Required environment variables are documented.
* [ ] The Docker image is added to `scripts/build_images.sh`.
* [ ] The container is added to `run_experiment.py`.
* [ ] The container is connected to the virtual switch.
* [ ] The client is started during the experiment.
* [ ] Logs are redirected to `/tmp/*.log` or another documented location.
* [ ] The generated traffic appears in the PCAP file.
* [ ] The profile does not depend on external services unless explicitly documented.

---

## 11. Expected outputs

A correctly configured profile should produce one or more of the following outputs:

| Output           | Description                                                         |
| ---------------- | ------------------------------------------------------------------- |
| MQTT packets     | Telemetry messages captured in the experiment PCAP.                 |
| RTSP/UDP packets | Video traffic captured in the experiment PCAP.                      |
| Runtime logs     | Execution logs stored inside the container, commonly under `/tmp/`. |
| PCAP traffic     | Network trace generated by `tcpdump` at the switch level.           |
| CSV dataset      | Optional output generated later from the PCAP converter.            |

---

## 12. Design guidelines

When creating new profiles, prefer:

* dataset-driven behavior instead of fixed synthetic values;
* clear topic naming;
* configurable timing through environment variables;
* small and reproducible Docker images;
* explicit dependencies in the Dockerfile;
* graceful termination when the experiment ends;
* logs that help debug execution;
* payload formats representative of real IoT systems.

Avoid:

* hardcoded external IP addresses;
* dependencies on unavailable remote services;
* very large files without documentation;
* undocumented environment variables;
* profile-specific changes that break existing devices;
* modifying the MQTT broker or topology unless necessary.

---

## 13. Summary

Device profiles are the main extension unit of IoT-Zoo. Each profile packages a dataset, runtime logic and protocol behavior into a Docker container. The experiment orchestrator then instantiates these profiles as network nodes, connects them to the emulated topology and captures the resulting traffic.

This structure allows IoT-Zoo to be extended with new datasets, domains and protocols while preserving a consistent execution workflow.
