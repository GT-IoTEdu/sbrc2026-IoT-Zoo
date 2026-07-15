# Troubleshooting

Start with:

```bash
./scripts/check_environment.sh
```

## Docker permission denied

If Docker works with `sudo` but not as your user, reboot or reload the Docker group:

```bash
sudo reboot
# or
newgrp docker
```

Then verify:

```bash
groups
docker ps
```

## Containernet import fails

The run scripts set `PYTHONPATH` automatically using `CONTAINERNET_PATH`, defaulting to `~/containernet`.

Check:

```bash
ls ~/containernet
./scripts/check_environment.sh
```

Manual debugging fallback:

```bash
sudo -E PYTHONPATH=$HOME/containernet python3 run_experiment.py --dry-run
```

A real network run still requires Containernet and root privileges.

## PyYAML is missing

The configurable topology loader requires PyYAML:

```bash
python3 -m pip install --user pyyaml
sudo python3 -m pip install pyyaml
```

## Topology validation fails

Run dry-run directly:

```bash
./scripts/run_full.sh --topology topology.yaml --dry-run
```

Common causes:

- unknown `template` name in `profiles`;
- duplicated IP address;
- missing `ip_pool` for replicated services;
- device profile scaled without `variants` or `vary`;
- node attached to a switch that was not declared;
- capture point referencing an unknown switch.

## Compressed dataset is invalid

If `unxz` reports that an `.xz` file has an unrecognized format, validate all compressed datasets:

```bash
find devices -name "*.xz" -print0 | while IFS= read -r -d '' f; do
  if ! xz -t "$f" >/dev/null 2>&1; then
    echo "INVALID: $f"
  fi
done
```

Replace or recompress invalid files before running the full topology.

## Basic demo data not prepared

Prepare it with:

```bash
./scripts/prepare_demo_data.sh --duration 120 --clean
```

Then build and run:

```bash
./scripts/build_images.sh --demo
./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_demo.pcap
```

## Docker image missing

Build the required images:

```bash
./scripts/build_images.sh --demo
# or
./scripts/build_images.sh --full
```

## PCAP file is empty or missing

Use an output path under `/tmp` and run long enough to generate traffic:

```bash
./scripts/run_full.sh --time 120 --output /tmp/iot_zoo_full.pcap
ls -lh /tmp/iot_zoo_full.pcap
```

For MQTT traffic inspection:

```bash
tcpdump -r /tmp/iot_zoo_full.pcap -n port 1883 -c 10
```
