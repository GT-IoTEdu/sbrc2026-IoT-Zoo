# Attack "UDP Flood"

> UDP packet flood.

## Metadata

| Field | Value |
|---|---|
| ID | `dos_udp_flood` |
| Category | 6) Denial of Service and Impact |
| Subcategory | 6.1 Network/transport floods (ICMP/TCP/UDP) |
| Image | `attack-udp-flood:latest` |
| Container | `attack-udp-flood` |
| Suggested max runtime | `10s` |
| Typical targets/services | `target IP service` |
| MITRE ATT&CK | [https://attack.mitre.org/tactics/TA0040/](https://attack.mitre.org/tactics/TA0040/)<br>[https://attack.mitre.org/techniques/T1498/](https://attack.mitre.org/techniques/T1498/)<br>[https://attack.mitre.org/techniques/T1498/001/](https://attack.mitre.org/techniques/T1498/001/) |

## Parameters

| Parameter | Type | Required | Default/placeholder | Description |
|---|---|---|---|---|
| `--target_ip` | `ip` | yes | `__HOST_IP__` | Target IP address or FQDN |
| `--target_port` | `port` | no | `8080` | Target port |

## Intensity Parameters

| Parameter | Default |
|---|---|
| `duration_s` |  |
| `count` |  |
| `rate_pps` |  |
| `payload_size` |  |

## Capture Warning

> This attack can generate a large amount of data if captured until its automatic completion. For demonstrations, use less than 5 seconds of execution.

## Testbed Execution

Use the project CLI to preserve traceability through the declarative catalog:

```bash
python3 attackzoo.py run dos_udp_flood --target <TARGET>
```

Run the container directly for isolated validation:

```bash
docker run --rm -d --name attack-udp-flood attack-udp-flood:latest "<TARGET_IP>" "8080"
```

## Observability

- Use `python3 attackzoo.py experiment` to run controlled warmup/attack/cooldown windows.
- Expected artifacts include PCAP files, probe CSVs, optional telemetry, features, datasets, and reports under `experiments/`.
- Typical testbed target services: `target IP service`.
