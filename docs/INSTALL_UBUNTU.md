# Installing IoT-Zoo on Ubuntu Server 20.04 LTS

The officially recommended environment is Ubuntu Server 20.04 LTS.

## 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-name>
```

## 2. Install system dependencies

```bash
./scripts/install_ubuntu.sh
```

If the installer adds your user to the Docker group, close and reopen the terminal before continuing.

## 3. Check the environment

```bash
./scripts/check_environment.sh
```

Resolve any `[FAIL]` item before running an experiment.

## 4. Prepare the minimal demo data

The demo data is generated from the compressed Urban Observatory datasets already stored under `devices/urban_observatory/`.

```bash
./scripts/prepare_demo_data.sh --duration 120 --clean
```

## 5. Build demo images

```bash
./scripts/build_images.sh --demo
```

## 6. Run the minimal demo

```bash
./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_demo.pcap
```

Check the output:

```bash
ls -lh /tmp/iot_zoo_demo.pcap
```

## 7. Build and run the full topology

After the demo works, build all images and run the full topology:

```bash
./scripts/build_images.sh --full
./scripts/run_full.sh --time 600 --output /tmp/iot_zoo_full.pcap
```

The full build requires all datasets referenced by the profile Dockerfiles to be present in their expected folders.
