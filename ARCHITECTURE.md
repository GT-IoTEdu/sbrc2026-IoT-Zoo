# IoT-Zoo architecture

IoT-Zoo is organized as a configuration-driven emulation framework.

## Layers

1. **Device profile layer**
   - Dockerfiles and client code under `devices/`.
   - Each profile represents an IoT gateway, device, broker, server, or consumer.

2. **Catalog layer**
   - `catalog.yaml` defines reusable templates for device profiles.
   - A template declares image, domain, protocol, startup command, default environment variables, volumes, privileges, and optional diversity variants.

3. **Topology layer**
   - `topology.yaml` and other topology files compose experiments from catalog templates.
   - Users can configure switches, links, services, profiles, IPs, NAT, capture points, duration, and output paths without editing Python code.

4. **Expansion and validation layer**
   - `topology_loader.py` expands a topology into an effective execution plan.
   - This layer is pure Python and does not import Containernet/Mininet, enabling dry-run validation on any machine with Python and PyYAML.

5. **Orchestration layer**
   - `run_experiment.py` consumes the expanded plan and launches Containernet.
   - It creates switches, Docker nodes, links, NAT, routes, services, device clients, and tcpdump captures.

6. **Execution scripts**
   - `scripts/run_demo.sh` runs the basic validation demo.
   - `scripts/run_full.sh` runs or dry-runs configurable full topologies.
   - `scripts/check_environment.sh` validates the host and the topology configuration.

## Default scenario

The default `topology.yaml` reproduces the original single-switch IoT-Zoo scenario. This preserves the original behavior while enabling custom scenarios through additional topology files.

## Custom scenarios

Custom topologies can add multiple switches, impaired links, different profile selections, multiple brokers, and multiple capture points. See `docs/CUSTOM_TOPOLOGIES.md` and `topology_example_tree.yaml`.

## Reproducibility

Use `--dump-config` to store the fully expanded topology used in an experiment:

```bash
./scripts/run_full.sh --topology topology_example_tree.yaml --time 120 --dump-config effective_tree.yaml --dry-run
```

This file records assigned IPs, expanded generated profiles, resolved defaults, service lists, and capture configuration.
