# IoT-Zoo L3-segmented institutional topology

This branch adds a robust routed topology mode to IoT-Zoo. The goal is to move beyond a flat L2 experiment while preserving the original IoT-Zoo device diversity and reproducibility.

## Figures

- Main topology figure: `docs/figures/l3_segmented_topology.png`
- Legend and notes panel: `docs/figures/l3_topology_legend.png`

## Main idea

The topology is organized into routed L3 segments. Each segment has an independent `/24` subnet, a local L2 switch, a gateway interface on a Linux router, and optional link parameters such as bandwidth, delay, jitter and loss.

The proposed institutional scenario has three logical layers:

1. **External / Threat / Human-user segment**: emulates external users, mobile applications, dashboards, scanner nodes and future attacker nodes.
2. **Cloud / Infrastructure / Services segment**: hosts the central MQTT broker, RTSP server, IDS/logging placeholders and monitoring components.
3. **Field domains**: six independent IoT domains, each with its own switch, subnet and local MQTT broker.

## Exact addressing plan

| Segment | Network | Gateway | Switch | Main nodes |
|---|---:|---:|---|---|
| External / Threat / User | `10.10.0.0/24` | `10.10.0.1` (`r_edge`) | `sw_external` | `attacker_node`, `scanner_node`, `benign_dashboard`, `mobile_app_user`, `external_client` |
| Cloud / Infra / Services | `10.20.0.0/24` | `10.20.0.1` (`r_edge`) | `sw_infra` | `broker_core`, `rtsp_server`, `ids_collector`, `log_mgmt` |
| Hospital | `10.30.1.0/24` | `10.30.1.1` (`r_field`) | `sw_hospital` | health/wearable/building profiles |
| University / Campus | `10.30.2.0/24` | `10.30.2.1` (`r_field`) | `sw_university` | campus/building profiles |
| Industrial / Facilities | `10.30.3.0/24` | `10.30.3.1` (`r_field`) | `sw_industrial` | industrial/facilities profiles |
| School | `10.30.4.0/24` | `10.30.4.1` (`r_field`) | `sw_school` | school/building profiles |
| Security / CCTV | `10.30.5.0/24` | `10.30.5.1` (`r_field`) | `sw_cctv` | RTSP cameras and stream consumer |
| Outdoor / Smart city / Agriculture | `10.30.6.0/24` | `10.30.6.1` (`r_field`) | `sw_outdoor` | urban observatory, weather, water and agriculture profiles |

## Routers

### `r_edge`

`r_edge` is the L3 boundary between the external segment and the infrastructure segment.

| Interface | Network | IP |
|---|---|---:|
| `r_edge-ext` | external | `10.10.0.1/24` |
| `r_edge-infra` | infra | `10.20.0.1/24` |

Static route:

```bash
ip route replace 10.30.0.0/16 via 10.20.0.254
```

Firewall preset: `edge_restricted`.

By default, only benign external clients are allowed to reach `broker_core` on TCP/1883. Scanner/attacker containers are present but do not automatically generate traffic and are blocked by default unless explicit ACL rules are added for an attack scenario.

### `r_field`

`r_field` aggregates all field domains and connects them to the infrastructure segment.

| Interface | Network | IP |
|---|---|---:|
| `r_field-infra` | infra | `10.20.0.254/24` |
| `r_field-hosp` | hospital | `10.30.1.1/24` |
| `r_field-univ` | university | `10.30.2.1/24` |
| `r_field-ind` | industrial | `10.30.3.1/24` |
| `r_field-school` | school | `10.30.4.1/24` |
| `r_field-cctv` | cctv | `10.30.5.1/24` |
| `r_field-out` | outdoor | `10.30.6.1/24` |

Static route:

```bash
ip route replace default via 10.20.0.1
```

Firewall preset: `field_microsegmentation`.

The default policy blocks direct east-west forwarding among field domains, for example hospital -> industrial or school -> CCTV. North-south flows between field domains and infrastructure are allowed.

## MQTT organization

The topology uses one broker per domain:

| Broker | IP | Network |
|---|---:|---|
| `broker_core` | `10.20.0.100` | infra |
| `broker_hospital` | `10.30.1.100` | hospital |
| `broker_university` | `10.30.2.100` | university |
| `broker_industrial` | `10.30.3.100` | industrial |
| `broker_school` | `10.30.4.100` | school |
| `broker_security` | `10.30.5.100` | cctv |
| `broker_outdoor` | `10.30.6.100` | outdoor |

IoT devices publish to their local broker. Local brokers are configured with a one-way Mosquitto bridge to `broker_core`:

```mosquitto
connection bridge_to_core
address 10.20.0.100:1883
try_private false
start_type automatic
topic # out 0
```

This preserves local domain traffic while enabling central aggregation.

## Benign external traffic

The external segment includes both attack placeholders and benign human/application clients:

| Node | IP | Behavior |
|---|---:|---|
| `attacker_node` | `10.10.0.10` | reserved for future attack scenarios |
| `scanner_node` | `10.10.0.20` | reserved for future scanning scenarios |
| `benign_dashboard` | `10.10.0.30` | publishes dashboard heartbeat messages to `broker_core` |
| `mobile_app_user` | `10.10.0.40` | publishes mobile-app heartbeat messages to `broker_core` |
| `external_client` | `10.10.0.50` | subscribes to `broker_core` topics |

This avoids a simplistic assumption that all external traffic is malicious.

## Multi-point capture

The L3 topology captures traffic at all major observation points:

- `sw_infra`
- all six domain switches: `sw_hospital`, `sw_university`, `sw_industrial`, `sw_school`, `sw_cctv`, `sw_outdoor`
- selected router interfaces: `r_edge:external`, `r_edge:infra`, `r_field:infra`, and all `r_field` downstream interfaces

When the output is `/tmp/iot_zoo_l3.pcap`, multi-point capture generates files such as:

```text
/tmp/iot_zoo_l3_sw_infra.pcap
/tmp/iot_zoo_l3_sw_hospital.pcap
/tmp/iot_zoo_l3_r_edge_external.pcap
/tmp/iot_zoo_l3_r_field_hospital.pcap
```

## Running

Validate without launching Containernet:

```bash
python3 run_experiment.py --topology topology_l3_segmented_institutional.yaml --dry-run
```

Run through the helper script:

```bash
./scripts/run_l3.sh --time 120 --output /tmp/iot_zoo_l3.pcap
```

Equivalent explicit command:

```bash
./scripts/run_full.sh --topology topology_l3_segmented_institutional.yaml --time 120 --output /tmp/iot_zoo_l3.pcap
```

Dump the expanded effective configuration:

```bash
python3 run_experiment.py \
  --topology topology_l3_segmented_institutional.yaml \
  --dry-run \
  --dump-config /tmp/iot_zoo_l3_effective.yaml
```

## Quick validation after a run

Check that multi-point PCAPs were created:

```bash
ls -lh /tmp/iot_zoo_l3_*.pcap
```

Check MQTT packets:

```bash
tshark -r /tmp/iot_zoo_l3_sw_infra.pcap -Y mqtt -c 10
```

Check RTSP packets:

```bash
tshark -r /tmp/iot_zoo_l3_sw_cctv.pcap -Y rtsp -c 10
```

Check traffic crossing router interfaces:

```bash
tshark -r /tmp/iot_zoo_l3_r_field_hospital.pcap -c 10
```

## Implementation notes

The implementation remains backward-compatible with the original L2 topology files. If a topology YAML does not define `mode: l3`, `networks`, or `routers`, the old L2 behavior is used.

The L3 implementation adds:

- `networks` section for subnets, gateways, switches and per-segment link parameters;
- `routers` section for Linux routers, interfaces, static routes and firewall presets;
- `network` field in services/profiles to attach nodes to a subnet;
- automatic host default routes and static routes;
- router interface capture points using the syntax `router:network`, e.g., `r_field:hospital`;
- `edge_restricted` and `field_microsegmentation` ACL presets.
