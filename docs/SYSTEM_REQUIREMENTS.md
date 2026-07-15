# System requirements and portability

## Officially validated targets

```text
Ubuntu Server 20.04 LTS
Ubuntu Server 22.04 LTS
```

The framework may work on other Linux distributions, but they are not officially validated.

## Unsupported native environments

Windows, macOS, and WSL/WSL2 are not supported as native execution environments because IoT-Zoo depends on Docker, Open vSwitch, Containernet/Mininet, Linux network namespaces, privileged networking, and packet capture.

Use a Linux VM from Windows or macOS.

## Recommended resources

| Scenario | vCPU | RAM | Disk |
|---|---:|---:|---:|
| Basic demo | 2+ | 4 GB+ | 20 GB+ |
| Configurable full topology | 4+ | 8 GB+ | 40-50 GB+ |

## Required system packages

- Docker Engine or `docker.io`
- Open vSwitch
- Containernet/Mininet
- Python 3 and pip
- `tcpdump`
- `xz-utils`
- `ethtool`, `iproute2`, `iptables`, `net-tools`
- `tshark` for optional PCAP inspection/conversion

## Required Python packages

- PyYAML
- pandas
- paho-mqtt
- scapy
- scikit-learn

The installer attempts to install these for both the regular user and root/sudo context because Containernet execution uses elevated privileges.
