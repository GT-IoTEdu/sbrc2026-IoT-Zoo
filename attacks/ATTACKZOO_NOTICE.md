# AttackZoo integration notice

This folder contains IoT-Zoo-adapted attack containers derived from the
AttackZoo SBSEG26 repository supplied for integration. The upstream project
is distributed under the BSD 3-Clause License; see `ATTACKZOO_LICENSE`.

The Dockerfiles and entrypoints were adapted for Containernet execution:
containers do not auto-run attacks at image startup. IoT-Zoo starts each
attack through `run_experiment.py` after the configured warmup window using
an attack scenario YAML file.

Only attacks compatible with the current IoT-Zoo L3 topology were imported:
MQTT attacks, reconnaissance against reachable L3 infrastructure, and
controlled transport/network floods. Attacks requiring CoAP, XRCE-DDS,
Zenoh, HTTP application servers, SSH/Telnet/SMB services, DHCP/STP/CDP/ARP
L2 assumptions, or broker authentication were intentionally left out.
