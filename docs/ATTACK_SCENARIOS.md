# L3 attack scenario integration

This extension integrates selected AttackZoo-style attack containers with the
IoT-Zoo L3 segmented topology without duplicating the benign topology YAML.

## Design

The benign topology remains the source of truth:

```text
topology_l3_segmented_institutional.yaml
```

Attack behavior is layered at runtime with `--attack-scenario`:

```bash
sudo python3 run_experiment.py \
  --topology topology_l3_segmented_institutional.yaml \
  --attack-scenario attack_scenarios/mqtt_publisher_flood.yaml \
  --time 180 \
  --output /tmp/iot_zoo_l3.pcap
```

Each enabled attack becomes a dedicated Docker node attached to the configured
network, usually the external segment. The attack starts after `start_s` seconds
and is bounded by `duration_s`. This keeps the benign baseline stable and makes
single-attack and multi-attack experiments reproducible.

## Imported attacks

The current IoT-Zoo topology supports MQTT, RTSP/TCP service exposure, L3
reconnaissance and controlled transport/network floods. Therefore only the
following attacks were imported/adapted:

| Type | Purpose | Default target |
|---|---|---|
| `mqtt_publisher_flood` | MQTT publish flood | `broker_core:1883` |
| `mqtt_lwt_abuse` | MQTT Last Will abuse | `broker_core:1883` |
| `mqtt_qos_amplification` | MQTT QoS 2 state/traffic amplification | `broker_core:1883` |
| `ping_sweep` | ICMP host discovery | `10.20.0.0/24` |
| `port_scanner_tcp` | TCP service discovery | infra services |
| `port_scanner_udp` | UDP service discovery | infra services |
| `syn_flood` | controlled TCP SYN flood | `broker_core:1883` |
| `icmp_flood` | controlled ICMP flood | `broker_core` |
| `udp_flood` | controlled UDP flood | `rtsp_server:8554` |
| `fin_flood`, `rst_flood`, `psh_flood` | controlled TCP flag floods | `broker_core:1883` |

Attacks that require CoAP, XRCE-DDS, Zenoh, HTTP application services,
SSH/Telnet/SMB targets, MQTT authentication, or L2-local assumptions such as DHCP
starvation/STP/CDP/ARP spoofing were intentionally left out of the active
catalog for this topology.

## Build attack images

```bash
./scripts/build_images.sh --attacks
```

or build devices and attacks:

```bash
./scripts/build_images.sh --full-with-attacks
```

## Scenario YAML structure

```yaml
scenario:
  name: mqtt_publisher_flood_external
  default_network: external
  ip_start: 10.10.0.60

attacks:
  - name: atk_mqtt_publisher_flood_core
    type: mqtt_publisher_flood
    enabled: true
    target: broker_core
    target_port: 1883
    start_s: 35
    duration_s: 20
    params:
      count: 600
      delay_ms: 10
      payload_size: 128
      qos: 0
```

Supported fields:

- `type`: key from `attacks/attack_catalog.yaml`.
- `enabled`: allows keeping attacks in a scenario but disabling them.
- `network`: L3 network where the attack node will be placed. Defaults to `external`.
- `ip`: optional fixed source IP. If omitted, IoT-Zoo allocates a free IP starting from `scenario.ip_start`.
- `target`: service/profile name from the topology, such as `broker_core` or `rtsp_server`.
- `target_ip`: explicit target IP alternative.
- `targets`: list of service names/IPs for scanners.
- `target_net`: CIDR for sweep-style attacks.
- `start_s` and `duration_s`: attack timing relative to experiment start.
- `params`: attack-specific environment variables, normalized to uppercase.

## Validation

General L3 validation:

```bash
python3 scripts/validate_l3_pcaps.py \
  --pcap-dir /tmp \
  --prefix iot_zoo_l3 \
  --out-dir ./validation_l3_attack
```

Scenario-specific validation example:

```bash
python3 scripts/validate_l3_pcaps.py \
  --pcap-dir /tmp \
  --prefix iot_zoo_l3 \
  --out-dir ./validation_mqtt_publisher_flood \
  --expect-ip 10.10.0.60 \
  --expect-flow 10.10.0.60,10.20.0.100,1883 \
  --expect-port 1883
```

The validator writes `attack_expectations.csv` when expectation checks are used.

## Recommended campaign order

1. `benign-only` L3 baseline.
2. Isolated attacks, one scenario at a time.
3. Multi-attack scenarios after isolated attacks are validated.

This avoids contaminating the benign baseline and makes labels easier to define.


## v15 note: attack container routing

Attack images include `iproute2`/`iputils` so the L3 experiment runner can install default routes inside attack containers before delayed execution. Attack logs export `ip -4 addr` and `ip route` diagnostics to `/tmp/iot_zoo_l3_logs/<attack>.log`.
