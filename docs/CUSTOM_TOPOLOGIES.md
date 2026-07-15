# Custom topologies

IoT-Zoo supports configuration-driven full topologies. The Python orchestrator no longer needs to be edited to change the experiment layout. Users can change YAML files and validate them before launching Containernet.

## Configuration model

The model has two layers.

### 1. Catalog layer

[`catalog.yaml`](../catalog.yaml) defines reusable device profile templates. Each template may contain:

```yaml
building_monitor:
  image: myzoo/building_monitor
  domain: built_environment
  protocol: mqtt
  dcmd: /bin/bash
  start: python3 -u /client.py
  log: /tmp/${name}.log
  env:
    SLEEP_TIME: '5'
```

The catalog should be edited by developers who add or maintain device profiles, Docker images, startup commands, default environment variables, volumes, or protocol-specific behavior.

### 2. Topology layer

[`topology.yaml`](../topology.yaml) composes a concrete experiment from the catalog. It defines the network, infrastructure services, selected profiles, switches, links, and capture points.

```yaml
experiment:
  time: 600
  output: capture.pcap

network:
  subnet: 10.0.0.0/24
  nat: { name: nat0, ip: 10.0.0.254, switch: s1 }

switches:
  - { name: s1 }

services:
  - name: broker
    kind: mqtt_broker
    ip: 10.0.0.100
    ip_pool: 10.0.0.101-10.0.0.110
    image: myzoo/mqtt_broker
    dcmd: /bin/bash
    boot:
      - /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf -d &

profiles:
  - name: predio
    template: building_monitor
    ip: 10.0.0.2
    switch: s1
    env:
      MQTT_TOPIC_PUB: building
```

The topology layer is intended for experiment authors and operators. It should be possible to build many scenarios without modifying Python code.

## Validate without running

Use dry-run mode before launching a topology:

```bash
./scripts/run_full.sh --topology topology.yaml --dry-run
```

The output summarizes switches, services, profiles, protocols, domains, capture points, and warnings.

## Export the effective topology

For reproducibility, generate the fully expanded configuration:

```bash
./scripts/run_full.sh --topology topology_example_tree.yaml \
  --time 120 \
  --dump-config effective_tree.yaml \
  --dry-run
```

The output file contains the final resolved services and profiles after IP allocation, profile expansion, defaults, and CLI overrides.

## Multi-switch topologies

Topologies can declare multiple switches and inter-switch links. Link impairments are passed to Containernet's `TCLink`.

```yaml
switches:
  - { name: s1 }
  - { name: s2 }
  - { name: s3 }

links:
  - { a: s2, b: s1, bw: 100, delay: "2ms" }
  - { a: s3, b: s1, bw: 5, delay: "30ms", loss: 1 }
```

Each service or profile can choose its switch:

```yaml
profiles:
  - { name: ns_gw, template: nurse_stress, ip: 10.0.0.17, switch: s2 }
```

See [`topology_example_tree.yaml`](../topology_example_tree.yaml) for a complete example.

## Capture points

Packet capture points are declared by switch name:

```yaml
capture:
  points: [s1]
  bpf: "not port 6653"
```

Multiple capture points are supported. If more than one point is configured, output files are suffixed by switch name.

## Services versus profiles

### Services

Services are infrastructure components such as MQTT brokers and RTSP servers. Services may be replicated when an `ip_pool` is provided.

```bash
./scripts/run_full.sh --dry-run --brokers 2
```

For generic service scaling:

```bash
./scripts/run_full.sh --dry-run --scale broker=2
```

When multiple MQTT brokers exist, MQTT profiles default to the first broker unless the profile explicitly sets `broker` or `MQTT_BROKER_ADDR`.

### Device profiles

Device profiles represent IoT devices or gateways. IoT-Zoo does not silently clone device profiles. A profile with `count > 1` must provide a diversity pool.

This is accepted:

```yaml
profiles:
  - template: urban_sensor
    name_prefix: gw_air
    switch: s2
    count: 8
    ip_pool: 10.0.0.50-10.0.0.99
```

because `urban_sensor` has `variants` in `catalog.yaml`.

This is rejected:

```bash
./scripts/run_full.sh --dry-run --scale predio=2
```

because `predio` is a single explicit device profile and no diversity pool was provided.

## Inline diversity with `vary`

A topology can define its own diversity pool using `vary`:

```yaml
profiles:
  - template: urban_sensor
    name_prefix: gw_custom
    count: 3
    ip_pool: 10.0.0.80-10.0.0.90
    vary:
      TARGET_VARIABLE: [CO, NO2, O3]
      MQTT_TOPIC_PUB: [city/air/co, city/air/no2, city/air/o3]
```

All lists inside `vary` must have the same length.

## Filtering profiles

Keep only a domain or template:

```bash
./scripts/run_full.sh --dry-run --include smart_city
./scripts/run_full.sh --dry-run --include urban_sensor
```

Drop a domain or template:

```bash
./scripts/run_full.sh --dry-run --exclude cctv
```

`--include` and `--exclude` filter device profiles. Infrastructure services remain available unless removed from the YAML topology.

## Validation rules

The loader validates:

- unknown catalog templates;
- missing images;
- missing or duplicated node names;
- missing, invalid, duplicated, or out-of-subnet IP addresses;
- unknown switches in nodes, NAT, links, and capture points;
- exhausted IP pools;
- device scaling without diversity;
- invalid link impairment values;
- invalid YAML structure.

Errors are reported as concise messages and do not print Python tracebacks during normal CLI usage.

## Protocol extension path

The catalog contains a `protocol` field. Current included profiles use MQTT and RTSP. Adding protocols such as CoAP or DDS should be done by adding protocol-specific Docker images, startup commands, environment variables, services, and optional adapters, while keeping the topology orchestration layer unchanged.
