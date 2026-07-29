# Attack "MQTT Publisher Flood"

> MQTT publish flood to evaluate broker availability and behavior under load.

## Metadata

| Field | Value |
|---|---|
| ID | `iot_mqtt_publisher` |
| Category | 7) IoT |
| Subcategory | 7.1 IoT Protocols / MQTT |
| Image | `attack-mqtt-publisher:latest` |
| Container | `attack-mqtt-publisher` |
| Suggested max runtime | `10s` |
| Typical targets/services | `mqtt-broker` |
| MITRE ATT&CK | [https://attack.mitre.org/tactics/TA0040/](https://attack.mitre.org/tactics/TA0040/)<br>[https://attack.mitre.org/techniques/T1499/](https://attack.mitre.org/techniques/T1499/)<br>[https://attack.mitre.org/techniques/T1499/002/](https://attack.mitre.org/techniques/T1499/002/) |

## Parameters

| Parameter | Type | Required | Default/placeholder | Description |
|---|---|---|---|---|
| `--target_ip` | `ip` | yes | `__HOST_IP__` | Target IP address or FQDN |
| `--target_port` | `port` | no | `1883` | Target port |

## Intensity Parameters

| Parameter | Default |
|---|---|
| `count` | `1000` |
| `delay_ms` |  |
| `payload_size` |  |

## Testbed Execution

Use the project CLI to preserve traceability through the declarative catalog:

```bash
python3 attackzoo.py run iot_mqtt_publisher --target <TARGET>
```

Run the container directly for isolated validation:

```bash
docker run --rm -d --name attack-mqtt-publisher attack-mqtt-publisher:latest "<TARGET_IP>" "1883"
```

## Observability

- Use `python3 attackzoo.py experiment` to run controlled warmup/attack/cooldown windows.
- Expected artifacts include PCAP files, probe CSVs, optional telemetry, features, datasets, and reports under `experiments/`.
- Typical testbed target services: `mqtt-broker`.
