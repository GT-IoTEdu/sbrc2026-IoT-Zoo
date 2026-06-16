# System requirements and portability

## Officially supported systems

IoT-Zoo is currently tested and recommended on:

```text
Ubuntu Server 20.04 LTS
Ubuntu Server 22.04 LTS
```

These are the environments targeted by the installation script.

## Why the environment is restricted

IoT-Zoo is not a regular Python-only application. It requires system-level networking support, including:

* Linux network namespaces;
* Docker containers used as emulated hosts;
* Open vSwitch bridges and virtual links;
* Containernet/Mininet topology control;
* privileged routing and interface configuration;
* packet capture with `tcpdump`.

Small differences in kernel, Docker, Open vSwitch, Mininet, or Python packaging can affect execution. For reproducibility, use Ubuntu Server 20.04 LTS or Ubuntu Server 22.04 LTS.

## Requirements for other Linux systems

Other Linux distributions or Ubuntu versions are not officially supported, but advanced users may try to run IoT-Zoo if they provide compatible versions of:

| Component                                      | Required for                                         |
| ---------------------------------------------- | ---------------------------------------------------- |
| Docker Engine                                  | Running infrastructure and device profile containers |
| Open vSwitch                                   | Virtual switching and traffic aggregation            |
| Mininet/Containernet                           | Network topology orchestration                       |
| Python 3.8+                                    | Running orchestration and conversion scripts         |
| `pandas`                                       | Dataset-driven profile processing                    |
| `paho-mqtt`                                    | MQTT publishers/clients                              |
| `scapy`                                        | Optional PCAP conversion utilities                   |
| `scikit-learn`                                 | Optional conversion and analysis utilities           |
| `tcpdump`                                      | PCAP capture                                         |
| `tshark`                                       | Optional packet inspection/conversion                |
| `xz-utils`                                     | Reading compressed datasets                          |
| `ethtool`, `iproute2`, `iptables`, `net-tools` | Network setup and diagnostics                        |

If you use another system, run:

```bash
./scripts/check_environment.sh
```

The script will report missing components, but it will not attempt to install dependencies on unsupported systems.

## Unsupported environments

| Environment           | Status                   | Recommendation      |
| --------------------- | ------------------------ | ------------------- |
| Windows native        | Unsupported              | Use a Linux VM      |
| macOS native          | Unsupported              | Use a Linux VM      |
| WSL/WSL2              | Not recommended          | Use a Linux VM      |
| Ubuntu 24.04 or newer | Not officially validated | Advanced users only |
| Fedora/Debian/Arch    | Not officially supported | Advanced users only |

## Recommended VM path

When in doubt, create a clean Ubuntu Server 20.04 LTS or Ubuntu Server 22.04 LTS VM and follow `docs/INSTALL_UBUNTU.md`.
