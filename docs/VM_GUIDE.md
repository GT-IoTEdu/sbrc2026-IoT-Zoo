# VM guide

The recommended way to run IoT-Zoo from Windows or macOS is to create a Linux VM and install the project inside it.
## Recommended VM configuration

```text
Ubuntu Server 20.04 LTS or Ubuntu Server 22.04 LTS
4 vCPUs
8 GB RAM
40–50 GB disk
```

For the basic demo, 2 vCPUs and 4 GB RAM may be enough, but the full topology should use the recommended resources.

## Installation inside the VM

```bash
git clone <repository-url>
cd <repository-name>

chmod +x scripts/*.sh
chmod +x build_images.sh

./scripts/install_ubuntu.sh
```

If the installer adds your user to the Docker group, reboot the VM or log out and log in again before continuing:

```bash
sudo reboot
```

Then run:

```bash
./scripts/check_environment.sh
./scripts/prepare_demo_data.sh --duration 120 --clean
./scripts/build_images.sh --demo
./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_basic_demo.pcap
```

Check the generated capture:

```bash
ls -lh /tmp/iot_zoo_basic_demo.pcap
tcpdump -r /tmp/iot_zoo_basic_demo.pcap -n port 1883 -c 10
```

## Sharing output files

PCAP files are usually written to `/tmp`. Copy them to a shared folder or use `scp` from the host machine.

Example:

```bash
cp /tmp/iot_zoo_basic_demo.pcap ~/iot_zoo_basic_demo.pcap
```

## Why a VM is recommended

IoT-Zoo creates Docker containers, virtual switches, network namespaces, routes, and packet capture processes. A dedicated VM keeps these changes isolated from your main operating system.