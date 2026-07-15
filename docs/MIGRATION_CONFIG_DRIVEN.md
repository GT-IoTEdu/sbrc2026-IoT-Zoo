# Migration to the configuration-driven orchestrator

This version replaces the hard-coded full topology in `run_experiment.py` with a declarative orchestrator driven by `catalog.yaml` and `topology.yaml`.

The default `topology.yaml` preserves the original single-switch IoT-Zoo experiment while enabling new custom topologies without editing Python code.

## Main changes

| File | Purpose |
|---|---|
| `run_experiment.py` | Generic full-topology orchestrator. Reads the expanded plan and launches Containernet. |
| `topology_loader.py` | Pure YAML expansion and validation layer. Does not import Mininet/Containernet. |
| `catalog.yaml` | Reusable device profile catalog. |
| `topology.yaml` | Default topology equivalent to the original full IoT-Zoo scenario. |
| `topology_example_tree.yaml` | Example with 3 switches, link impairment, 2 brokers, and generated profiles. |
| `scripts/run_full.sh` | Runs or dry-runs configurable topologies. |
| `scripts/check_environment.sh` | Validates the host and configuration-driven topology files. |
| `requirements.txt` | Lists required Python packages, including PyYAML. |

## Backward-compatible default behavior

The default topology expands to:

```text
2 services: broker, v_srv
43 device profiles
1 NAT
46 total containers
```

Validate it with:

```bash
./scripts/run_full.sh --topology topology.yaml --dry-run
```

Run it with:

```bash
./scripts/run_full.sh --time 600 --output /tmp/iot_zoo_full.pcap
```

## Dry-run and reproducibility

Dry-run mode validates and summarizes the topology without launching Containernet:

```bash
./scripts/run_full.sh --topology topology_example_tree.yaml --dry-run
```

The fully expanded effective configuration can be saved:

```bash
./scripts/run_full.sh --topology topology_example_tree.yaml \
  --time 120 \
  --dump-config effective_tree.yaml \
  --dry-run
```

This records generated names, allocated IP addresses, defaults, services, links, and capture points.

## Customization model

Users compose experiments in YAML. Developers add new profile types in `devices/`, `scripts/build_images.sh`, and `catalog.yaml`.

Examples:

```bash
./scripts/run_full.sh --dry-run --include smart_city
./scripts/run_full.sh --dry-run --exclude cctv
./scripts/run_full.sh --dry-run --brokers 2
./scripts/run_full.sh --topology topology_example_tree.yaml --time 120 --output /tmp/iot_zoo_tree.pcap
```

## Diversity rule

Infrastructure services can be replicated when an IP pool is available.

Device profiles are not silently cloned. A device profile with `count > 1` must provide distinct variants through either:

- `variants` in `catalog.yaml`; or
- `vary` directly in the topology file.

This keeps the IoT-Zoo diversity principle explicit and reproducible.

## Validation performed before launch

The loader checks unknown templates, missing images, duplicated names, duplicated IPs, out-of-subnet IPs, invalid switches, invalid links, invalid capture points, exhausted IP pools, and profile scaling without diversity.
