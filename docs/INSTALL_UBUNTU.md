# Installing IoT-Zoo on Ubuntu Server 20.04/22.04 LTS

The officially recommended environments are Ubuntu Server 20.04 LTS and Ubuntu Server 22.04 LTS.

## 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-name>
```

## 2. Enable script execution

```bash
chmod +x scripts/*.sh
chmod +x build_images.sh
```

## 3. Install system dependencies

```bash
./scripts/install_ubuntu.sh
```

If the installer adds your user to the Docker group, reboot the VM or log out and log in again before continuing:

```bash
sudo reboot
```

## 4. Check the environment

```bash
./scripts/check_environment.sh
```

Resolve any `[FAIL]` item before running an experiment.

## 5. Prepare the basic demo data

The basic demo data is generated from the compressed Urban Observatory datasets already stored under `devices/urban_observatory/`.

```bash
./scripts/prepare_demo_data.sh --duration 120 --clean
```

## 6. Build basic demo images

```bash
./scripts/build_images.sh --demo
```

## 7. Run the basic demo

```bash
./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_basic_demo.pcap
```

Check the output:

```bash
ls -lh /tmp/iot_zoo_basic_demo.pcap
tcpdump -r /tmp/iot_zoo_basic_demo.pcap -n port 1883 -c 10
```

## 8. Build and run the full topology

After the basic demo works, build all images and run the full topology:

```bash
./scripts/build_images.sh --full
./scripts/run_full.sh --time 600 --output /tmp/iot_zoo_full.pcap
```

The full build requires all datasets referenced by the profile Dockerfiles to be present in their expected folders.