# Installing IoT-Zoo on Ubuntu Server

Recommended targets:

```text
Ubuntu Server 20.04 LTS
Ubuntu Server 22.04 LTS
```

IoT-Zoo requires Docker, Open vSwitch, Containernet/Mininet, Python 3, `tcpdump`, `xz-utils`, and several Python packages including PyYAML.

## Fresh installation

```bash
git clone <repository-url>
cd <repository-name>
chmod +x scripts/*.sh build_images.sh run_experiment.py demo_experiment.py topology_loader.py
./scripts/install_ubuntu.sh
```

If the installer adds your user to the Docker group, reboot or close and reopen the terminal.

## Validate the environment

```bash
./scripts/check_environment.sh
```

This checks the host environment and also validates both the default and example configurable topologies in dry-run mode.

## Run the basic demo

```bash
./scripts/prepare_demo_data.sh --duration 120 --clean
./scripts/build_images.sh --demo
./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_demo.pcap
ls -lh /tmp/iot_zoo_demo.pcap
tcpdump -r /tmp/iot_zoo_demo.pcap -n port 1883 -c 10
```

## Run the configurable full topology

```bash
./scripts/build_images.sh --full
./scripts/run_full.sh --topology topology.yaml --dry-run
./scripts/run_full.sh --time 600 --output /tmp/iot_zoo_full.pcap
```

## Run an example custom topology

```bash
./scripts/run_full.sh --topology topology_example_tree.yaml --dry-run
./scripts/run_full.sh --topology topology_example_tree.yaml --time 120 --output /tmp/iot_zoo_tree.pcap
```
