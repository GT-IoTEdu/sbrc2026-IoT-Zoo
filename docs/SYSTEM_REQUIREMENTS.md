# System requirements and portability

## Officially supported system

IoT-Zoo is currently tested and recommended on:

```text
Ubuntu Server 20.04 LTS
```

This is the only environment targeted by the installation script.

## Why the environment is restricted

IoT-Zoo is not a regular Python-only application. It requires system-level networking support, including:

- Linux network namespaces;
- Docker containers used as emulated hosts;
- Open vSwitch bridges and virtual links;
- Containernet/Mininet topology control;
- privileged routing and interface configuration;
- packet capture with `tcpdump`.

Small differences in kernel, Docker, Open vSwitch, Mininet, or Python packaging can break the execution. For reproducibility, use the official Ubuntu Server 20.04 LTS baseline.

## Requirements for other Linux systems

Other Linux distributions are not officially supported, but advanced users may try to run IoT-Zoo if they provide compatible versions of:

| Component | Required for |
|---|---|
| Docker Engine | Running infrastructure and device profile containers |
| Open vSwitch | Virtual switching and traffic aggregation |
| Mininet/Containernet | Network topology orchestration |
| Python 3 | Running orchestration and conversion scripts |
| `pandas` | Dataset-driven profile processing |
| `paho-mqtt` | MQTT publishers/clients |
| `scapy` | Optional PCAP conversion utilities |
| `tcpdump` | PCAP capture |
| `tshark` | Optional packet inspection/conversion |
| `xz-utils` | Extracting compressed datasets |
| `ethtool`, `iproute2`, `iptables`, `net-tools` | Network setup and diagnostics |

If you use another system, run:

```bash
./scripts/check_environment.sh
```

The script will report missing components, but it will not attempt to install dependencies on unsupported systems.

## Unsupported environments

| Environment | Status | Recommendation |
|---|---|---|
| Windows native | Unsupported | Use a Linux VM |
| macOS native | Unsupported | Use a Linux VM |
| WSL/WSL2 | Not recommended | Use a Linux VM |
| Ubuntu 22.04/24.04 | Not officially supported | Validate manually before use |
| Fedora/Debian/Arch | Not officially supported | Advanced users only |

## Recommended VM path

When in doubt, create a clean Ubuntu Server 20.04 LTS VM and follow `docs/INSTALL_UBUNTU.md`.
