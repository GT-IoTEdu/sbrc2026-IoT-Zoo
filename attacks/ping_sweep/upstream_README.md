# Attack "Ping Sweep"

> ICMP sweep for host discovery.

## Metadata

| Field | Value |
|---|---|
| ID | `recon_ping_sweep` |
| Category | 1) Reconnaissance and Discovery |
| Subcategory | 1.1 Network-level host discovery |
| Image | `attack-ping-sweep:latest` |
| Container | `attack-ping-sweep` |
| Suggested max runtime | `10s` |
| Typical targets/services | `local network` |
| MITRE ATT&CK | [https://attack.mitre.org/tactics/TA0043/](https://attack.mitre.org/tactics/TA0043/)<br>[https://attack.mitre.org/tactics/TA0007/](https://attack.mitre.org/tactics/TA0007/)<br>[https://attack.mitre.org/techniques/T1590/](https://attack.mitre.org/techniques/T1590/)<br>[https://attack.mitre.org/techniques/T1595/](https://attack.mitre.org/techniques/T1595/)<br>[https://attack.mitre.org/techniques/T1595/001/](https://attack.mitre.org/techniques/T1595/001/)<br>[https://attack.mitre.org/techniques/T1018/](https://attack.mitre.org/techniques/T1018/) |

## Parameters

| Parameter | Type | Required | Default/placeholder | Description |
|---|---|---|---|---|
| `--target_net` | `cidr` | yes | `192.168.0.0/24` | Target network |

## Testbed Execution

Use the project CLI to preserve traceability through the declarative catalog:

```bash
python3 attackzoo.py run recon_ping_sweep --target <TARGET>
```

Run the container directly for isolated validation:

```bash
docker run --rm -d --name attack-ping-sweep attack-ping-sweep:latest "192.168.0.0/24"
```

## Observability

- Use `python3 attackzoo.py experiment` to run controlled warmup/attack/cooldown windows.
- Expected artifacts include PCAP files, probe CSVs, optional telemetry, features, datasets, and reports under `experiments/`.
- Typical testbed target services: `local network`.
