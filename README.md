# IoT-Zoo

IoT-Zoo is a container-based framework for reproducible IoT traffic emulation. It uses Docker containers as heterogeneous IoT device profiles inside a Containernet/Mininet topology, generating MQTT and RTSP traffic that can be captured as PCAP and later converted for analysis.

The project supports two execution styles:

- **Basic demo:** a small two-device validation scenario for checking installation quickly.
- **Configurable full topology:** a YAML-driven topology engine where users select device profiles, switches, links, services, capture points, and scaling options without editing Python code.

## Supported environment

Recommended and validated targets:

```text
Ubuntu Server 20.04 LTS
Ubuntu Server 22.04 LTS
```

IoT-Zoo uses Linux network namespaces, Docker, Open vSwitch, Containernet/Mininet, privileged network operations, and packet capture. Windows, macOS, and WSL/WSL2 are not supported as native execution environments. Use a Linux VM when working from Windows or macOS.

Recommended resources:

| Scenario | vCPU | RAM | Disk |
|---|---:|---:|---:|
| Basic demo | 2+ | 4 GB+ | 20 GB+ |
| Configurable full topology | 4+ | 8 GB+ | 40-50 GB+ |

Other Linux distributions may work, but they are not officially validated. See [`docs/SYSTEM_REQUIREMENTS.md`](docs/SYSTEM_REQUIREMENTS.md).

## Quick start on a fresh Ubuntu Server VM

```bash
git clone <repository-url>
cd <repository-name>

chmod +x scripts/*.sh build_images.sh run_experiment.py demo_experiment.py topology_loader.py
./scripts/install_ubuntu.sh
```

After installation, reboot or close and reopen the terminal if the script added your user to the Docker group. Then run:

```bash
./scripts/check_environment.sh
./scripts/prepare_demo_data.sh --duration 120 --clean
./scripts/build_images.sh --demo
./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_demo.pcap
```

Check the generated capture:

```bash
ls -lh /tmp/iot_zoo_demo.pcap
tcpdump -r /tmp/iot_zoo_demo.pcap -n port 1883 -c 10
```

## Running the configurable full topology

Build all Docker images:

```bash
./scripts/build_images.sh --full
```

Validate the default full topology without launching the network:

```bash
./scripts/run_full.sh --topology topology.yaml --dry-run
```

Run the default full topology:

```bash
./scripts/run_full.sh --time 600 --output /tmp/iot_zoo_full.pcap
```

The default `topology.yaml` reproduces the original single-switch IoT-Zoo scenario using the declarative configuration system.

## Custom topologies

IoT-Zoo now separates reusable device definitions from experiment composition:

- [`catalog.yaml`](catalog.yaml) defines reusable device profile templates: Docker image, protocol, domain, default environment, startup command, volumes, and optional diversity variants.
- [`topology.yaml`](topology.yaml) defines the default experiment: services, selected profiles, IPs, switches, links, NAT, capture points, and duration.
- [`topology_example_tree.yaml`](topology_example_tree.yaml) shows a custom multi-switch topology with link impairments and multiple brokers.
- [`topology_loader.py`](topology_loader.py) expands and validates configurations without importing Mininet, so topologies can be checked in dry-run mode.

Example dry-run with the tree topology:

```bash
./scripts/run_full.sh --topology topology_example_tree.yaml --dry-run
```

Write the fully expanded effective configuration for reproducibility:

```bash
./scripts/run_full.sh --topology topology_example_tree.yaml \
  --time 120 \
  --dump-config effective_tree.yaml \
  --dry-run
```

Run a custom topology:

```bash
./scripts/run_full.sh --topology topology_example_tree.yaml \
  --time 120 \
  --output /tmp/iot_zoo_tree.pcap
```

Filter profiles by domain or template:

```bash
./scripts/run_full.sh --dry-run --include smart_city
./scripts/run_full.sh --dry-run --exclude cctv
```

Scale infrastructure services, such as MQTT brokers:

```bash
./scripts/run_full.sh --dry-run --brokers 2
```

Scale device profiles only when a diversity pool is declared through `vary` in the topology or `variants` in the catalog. IoT-Zoo intentionally refuses silent cloning of the same device profile.

See [`docs/CUSTOM_TOPOLOGIES.md`](docs/CUSTOM_TOPOLOGIES.md) for the configuration model and examples.

## Repository structure

```text
.
├── README.md
├── run_experiment.py              # Configurable full-topology orchestrator
├── topology_loader.py             # Pure YAML expansion and validation layer
├── catalog.yaml                   # Reusable device profile catalog
├── topology.yaml                  # Default full topology
├── topology_example_tree.yaml     # Multi-switch custom topology example
├── demo_experiment.py             # Basic demo topology orchestrator
├── build_images.sh                # Compatibility wrapper for scripts/build_images.sh
├── scripts/
│   ├── install_ubuntu.sh          # Install dependencies on Ubuntu Server
│   ├── check_environment.sh       # Diagnose the host environment
│   ├── prepare_demo_data.sh       # Generate small demo data from .csv.xz files
│   ├── build_images.sh            # Build demo or full Docker images
│   ├── run_demo.sh                # Run a small end-to-end demo
│   └── run_full.sh                # Run configurable full topologies
├── docs/
│   ├── CUSTOM_TOPOLOGIES.md
│   ├── INSTALL_UBUNTU.md
│   ├── SYSTEM_REQUIREMENTS.md
│   ├── DATASETS.md
│   ├── TROUBLESHOOTING.md
│   └── VM_GUIDE.md
├── sample_data/
│   └── urban_observatory/         # Generated small demo data
├── devices/                       # Device profile source code, Dockerfiles, and datasets
└── convert_pcap_to_csv/           # PCAP-to-CSV conversion utilities
```

## Scripts

| Script | Purpose |
|---|---|
| `scripts/install_ubuntu.sh` | Installs system and Python dependencies on Ubuntu Server 20.04/22.04 LTS. |
| `scripts/check_environment.sh` | Checks OS, Docker, Open vSwitch, Python packages, Containernet, topology dry-runs, datasets, and images. |
| `scripts/prepare_demo_data.sh` | Samples a small basic-demo dataset from the full Urban Observatory `.csv.xz` files. |
| `scripts/build_images.sh --demo` | Builds only the images needed by the basic demo. |
| `scripts/build_images.sh --full` | Builds all available device images. |
| `scripts/run_demo.sh` | Runs the basic demo scenario and writes a PCAP file. |
| `scripts/run_full.sh` | Runs or dry-runs the configurable full topology and writes a PCAP file. |

## Dataset organization

Datasets are stored with the device profiles that use them. Most profiles follow this pattern:

```text
devices/<profile_name>/
├── Dockerfile
├── client.py
└── <dataset-folder-or-file>.csv.xz
```

The basic demo does not duplicate full datasets. It generates small CSV samples under `sample_data/urban_observatory/` using:

```bash
./scripts/prepare_demo_data.sh --duration 120 --clean
```

See [`docs/DATASETS.md`](docs/DATASETS.md) for details.

## Output files

Typical outputs include:

- `.pcap`: network capture generated by `tcpdump`.
- `/tmp/*.log`: service and device logs generated during execution.
- `.csv`: optional processed output generated by `convert_pcap_to_csv/`.
- expanded topology YAML files produced with `--dump-config`.

Saving PCAP files to `/tmp` is recommended because packet capture runs with elevated privileges.

## Troubleshooting

Start with:

```bash
./scripts/check_environment.sh
```

Common issues and fixes are documented in [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## Security note

IoT-Zoo creates privileged network namespaces, Docker containers, virtual links, Open vSwitch bridges, and packet capture processes. Run it inside a dedicated VM when possible. The included scenarios are intended to generate local emulated traffic only.

## License

See the repository license file. Keep this section consistent with the selected repository license before public release.

## L3-segmented institutional topology

This package also includes a routed L3 topology for the proposed institutional IoT-Zoo scenario:

```bash
python3 run_experiment.py --topology topology_l3_segmented_institutional.yaml --dry-run
./scripts/run_l3.sh --time 120 --output /tmp/iot_zoo_l3.pcap
```

The L3 topology uses independent subnets for the external/user segment, infrastructure services, and six field domains: hospital, university, industrial/facilities, school, CCTV, and outdoor/smart-city/agriculture. It adds Linux routers (`r_edge`, `r_field`), gateway configuration, static routes, ACL presets, local MQTT brokers with one-way bridge to `broker_core`, benign external clients, and multi-point PCAP capture.

See [`docs/L3_SEGMENTED_TOPOLOGY.md`](docs/L3_SEGMENTED_TOPOLOGY.md) for the exact IP plan and validation commands.

