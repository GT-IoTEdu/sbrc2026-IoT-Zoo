# VM guide

The recommended way to run IoT-Zoo from Windows or macOS is to create a Linux VM and install the project inside it.

## Recommended VM

```text
Ubuntu Server 22.04 LTS or 20.04 LTS
4 vCPUs
8 GB RAM
40-50 GB disk
NAT networking
```

The basic demo can run with 2 vCPUs, 4 GB RAM, and about 20 GB disk.

## Setup inside the VM

```bash
git clone <repository-url>
cd <repository-name>
chmod +x scripts/*.sh build_images.sh run_experiment.py demo_experiment.py topology_loader.py
./scripts/install_ubuntu.sh
sudo reboot
```

After reboot:

```bash
cd <repository-name>
./scripts/check_environment.sh
```

## First validation

```bash
./scripts/prepare_demo_data.sh --duration 120 --clean
./scripts/build_images.sh --demo
./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_demo.pcap
```

## Configurable full-topology validation

```bash
./scripts/build_images.sh --full
./scripts/run_full.sh --topology topology.yaml --dry-run
./scripts/run_full.sh --time 120 --output /tmp/iot_zoo_full.pcap
```

## Prebuilt VM image

If a prebuilt VM image is distributed, change any default password before exposing the VM to public networks. The image should contain no generated PCAP files, temporary logs, shell history, or temporary dataset-reduction scripts.
