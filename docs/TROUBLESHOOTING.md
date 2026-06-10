# Troubleshooting

Start with:

```bash
./scripts/check_environment.sh
```

Resolve `[FAIL]` items first. `[WARN]` items may be acceptable depending on the scenario.

## Unsupported operating system

IoT-Zoo is officially tested on Ubuntu Server 20.04 LTS. Other systems may work, but are not supported by the installer.

Use a VM if you are on Windows or macOS. WSL/WSL2 is not recommended because IoT-Zoo depends on Linux networking features, Open vSwitch, privileged namespaces, and packet capture.

## Docker is not reachable

Check the service:

```bash
sudo systemctl status docker
sudo systemctl start docker
```

If your user was added to the Docker group, close and reopen the terminal:

```bash
groups
```

You should see `docker` in the group list.

## Open vSwitch is not running

```bash
sudo systemctl status openvswitch-switch
sudo systemctl start openvswitch-switch
```

## Containernet cannot be imported

The run scripts set `PYTHONPATH` internally. If you installed Containernet outside the default location, set:

```bash
export CONTAINERNET_PATH=/path/to/containernet
```

Then retry:

```bash
./scripts/check_environment.sh
```

Manual fallback:

```bash
sudo -E PYTHONPATH=$CONTAINERNET_PATH python3 run_experiment.py --time 60 --output /tmp/test.pcap
```

This command is only for debugging. Normal usage should go through `scripts/run_demo.sh` or `scripts/run_full.sh`.

## Minimal demo says sample data is missing

Generate demo data from the compressed Urban Observatory datasets:

```bash
./scripts/prepare_demo_data.sh --duration 120 --clean
```

Then check:

```bash
find sample_data/urban_observatory -name "*.csv"
```

If the preparation script fails, verify that these source files exist under `devices/urban_observatory/`:

```text
CO dataset, for example 2025-CO.csv.xz
NO2 dataset, for example 2025-NO2.csv.xz
Internal Temperature dataset, usually under the building domain
```

## Docker image is missing

For the demo:

```bash
./scripts/build_images.sh --demo
```

For the full topology:

```bash
./scripts/build_images.sh --full
```

## Full image build fails with Docker COPY errors

A Docker `COPY` error usually means the dataset expected by that profile is not present in the folder referenced by its Dockerfile.

Check dataset layout:

```bash
find devices -name "*.csv.xz" -o -name "*.txt.xz" -o -name "*.mp4"
```

See `docs/DATASETS.md` for expected paths.

## PCAP file is empty or missing

Use `/tmp` for PCAP output because packet capture runs with elevated privileges:

```bash
./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_demo.pcap
ls -lh /tmp/iot_zoo_demo.pcap
```

Check logs:

```bash
ls -lh /tmp/*iot_zoo* /tmp/demo_*.log 2>/dev/null
```

## Stale containers remain after interruption

```bash
sudo docker rm -f $(sudo docker ps -aq --filter name=mn)
sudo mn -c
```
