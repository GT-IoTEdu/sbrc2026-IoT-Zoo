#!/usr/bin/env python3
"""
IoT-Zoo topology loader.

This module is intentionally independent from Containernet/Mininet. It reads a
YAML topology plus a YAML device catalog, expands auto-generated nodes, allocates
IPs, applies CLI overrides, and validates the resulting execution plan.

Supported topology modes:
  * L2 mode: backward-compatible IoT-Zoo topology with switches, optional
    inter-switch links, one subnet and optional Mininet NAT.
  * L3 mode: segmented/routed topology with multiple subnets, Linux routers,
    gateways, host routes, router routes, ACL presets and capture points on
    switches or router interfaces.

Design rules:
  * Services are infrastructure elements such as MQTT brokers, RTSP servers,
    IDS/log placeholders, external clients or other support containers.
  * Device profiles are not silently cloned. A profile count greater than one is
    accepted only when a diversity pool is provided through `vary` in the
    topology or `variants` in the catalog.
  * All node names, IPs, switches, links, capture points, router interfaces, and
    referenced catalog templates are validated before any network is launched.
"""

from __future__ import annotations

import copy
import ipaddress
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

import yaml


class TopologyError(ValueError):
    """Raised when a topology/catalog file is invalid."""


class IPPool:
    """Sequential IPv4 allocator over one or more range specifications."""

    def __init__(self, reserved: Optional[Iterable[str]] = None):
        self._used = set(reserved or [])

    def reserve(self, ip: Optional[str]) -> None:
        if ip:
            self._used.add(_strip_prefix(str(ip)))

    @staticmethod
    def expand_range(spec: str) -> List[str]:
        if not spec:
            raise TopologyError("empty ip_pool range")
        if "-" in str(spec):
            lo, hi = [s.strip() for s in str(spec).split("-", 1)]
        else:
            lo = hi = str(spec).strip()
        try:
            lo_i = int(ipaddress.IPv4Address(_strip_prefix(lo)))
            hi_i = int(ipaddress.IPv4Address(_strip_prefix(hi)))
        except ipaddress.AddressValueError as exc:
            raise TopologyError(f"invalid ip_pool range '{spec}': {exc}") from exc
        if hi_i < lo_i:
            raise TopologyError(f"invalid ip_pool range '{spec}': upper bound is smaller than lower bound")
        return [str(ipaddress.IPv4Address(i)) for i in range(lo_i, hi_i + 1)]

    def allocate(self, pool_spec: Any, n: int, owner: str = "node") -> List[str]:
        if n < 0:
            raise TopologyError(f"{owner}: requested a negative number of IPs")
        if n == 0:
            return []
        if not pool_spec:
            raise TopologyError(f"{owner}: count requires ip_pool, but no ip_pool was provided")

        ranges = pool_spec if isinstance(pool_spec, list) else [pool_spec]
        candidates: List[str] = []
        for spec in ranges:
            candidates.extend(self.expand_range(str(spec)))

        out: List[str] = []
        for ip in candidates:
            if len(out) == n:
                break
            if ip not in self._used:
                out.append(ip)
                self._used.add(ip)

        if len(out) != n:
            raise TopologyError(f"{owner}: ip_pool '{pool_spec}' exhausted; needed {n}, got {len(out)}")
        return out


def _strip_prefix(ip: str) -> str:
    return str(ip).split("/", 1)[0]


def _load_yaml(path: Union[str, os.PathLike]) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError as exc:
        raise TopologyError(f"file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise TopologyError(f"invalid YAML in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise TopologyError(f"top-level YAML document must be a mapping: {path}")
    return data


def _as_list(value: Any, field: str) -> List[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TopologyError(f"'{field}' must be a list")
    return value


def _subst(value: Any, mapping: Dict[str, Any]) -> Any:
    if isinstance(value, str):
        out = value
        for k, v in mapping.items():
            out = out.replace("${%s}" % k, str(v))
        return out
    if isinstance(value, list):
        return [_subst(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: _subst(v, mapping) for k, v in value.items()}
    return value


def _variant_combos(vary: Dict[str, Sequence[Any]], owner: str) -> List[Dict[str, Any]]:
    if not isinstance(vary, dict) or not vary:
        raise TopologyError(f"{owner}: 'vary' must be a non-empty mapping of equal-length lists")
    keys = list(vary.keys())
    lengths = set()
    for k in keys:
        if not isinstance(vary[k], list):
            raise TopologyError(f"{owner}: vary.{k} must be a list")
        lengths.add(len(vary[k]))
    if len(lengths) != 1:
        raise TopologyError(f"{owner}: all 'vary' lists must have the same length, got {sorted(lengths)}")
    n = lengths.pop()
    return [{k: vary[k][i] for k in keys} for i in range(n)]


def _parse_filter(values: Optional[Sequence[str]]) -> Optional[Set[str]]:
    if not values:
        return None
    out: Set[str] = set()
    for v in values:
        for item in str(v).split(","):
            item = item.strip()
            if item:
                out.add(item)
    return out or None


def _to_int(value: Any, field: str, minimum: Optional[int] = None) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise TopologyError(f"{field} must be an integer, got {value!r}") from exc
    if minimum is not None and out < minimum:
        raise TopologyError(f"{field} must be >= {minimum}, got {out}")
    return out


def _normalize_switches(raw_switches: Any) -> List[str]:
    switches = raw_switches or [{"name": "s1"}]
    if not isinstance(switches, list):
        raise TopologyError("switches must be a list")
    names: List[str] = []
    for i, sw in enumerate(switches):
        if isinstance(sw, str):
            name = sw
        elif isinstance(sw, dict):
            name = sw.get("name")
        else:
            raise TopologyError(f"switches[{i}] must be a string or mapping")
        if not name:
            raise TopologyError(f"switches[{i}] is missing name")
        if name in names:
            raise TopologyError(f"duplicate switch name: {name}")
        names.append(str(name))
    return names


def _first_mqtt_broker_ip(services: List[Dict[str, Any]]) -> Optional[str]:
    for service in services:
        if service.get("kind") == "mqtt_broker":
            return service.get("ip")
    return None


def _service_ip_by_name(services: List[Dict[str, Any]]) -> Dict[str, str]:
    return {s["name"]: s["ip"] for s in services}


def _parse_subnet(value: str, owner: str) -> ipaddress.IPv4Network:
    try:
        return ipaddress.IPv4Network(str(value), strict=False)
    except ValueError as exc:
        raise TopologyError(f"{owner}: invalid subnet '{value}': {exc}") from exc


def _prefixlen(subnet: str) -> int:
    return ipaddress.IPv4Network(str(subnet), strict=False).prefixlen


def _validate_ip(ip: str, owner: str, subnet: Optional[ipaddress.IPv4Network] = None) -> None:
    try:
        addr = ipaddress.IPv4Address(_strip_prefix(ip))
    except ipaddress.AddressValueError as exc:
        raise TopologyError(f"{owner}: invalid IP '{ip}'") from exc
    if subnet is not None and addr not in subnet:
        raise TopologyError(f"{owner}: IP {ip} is outside configured subnet {subnet}")


def _validate_cidr(value: str, owner: str) -> None:
    if str(value).lower() == "default":
        return
    try:
        ipaddress.IPv4Network(str(value), strict=False)
    except ValueError as exc:
        raise TopologyError(f"{owner}: invalid route destination '{value}': {exc}") from exc


def _normalise_networks(raw: Any, switches: Set[str]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    networks: Dict[str, Dict[str, Any]] = {}
    switch_to_network: Dict[str, str] = {}
    nets_seen: List[Tuple[str, ipaddress.IPv4Network]] = []

    for idx, net_raw in enumerate(_as_list(raw, "networks")):
        if not isinstance(net_raw, dict):
            raise TopologyError(f"networks[{idx}] must be a mapping")
        name = str(net_raw.get("name", "")).strip()
        if not name:
            raise TopologyError(f"networks[{idx}] is missing name")
        if name in networks:
            raise TopologyError(f"duplicate network name: {name}")
        sw = str(net_raw.get("switch", "")).strip()
        if not sw:
            raise TopologyError(f"network '{name}' is missing switch")
        if sw not in switches:
            raise TopologyError(f"network '{name}' references unknown switch '{sw}'")
        if sw in switch_to_network:
            raise TopologyError(
                f"switch '{sw}' is assigned to more than one L3 network: {switch_to_network[sw]} and {name}"
            )
        subnet_s = str(net_raw.get("subnet", "")).strip()
        if not subnet_s:
            raise TopologyError(f"network '{name}' is missing subnet")
        subnet = _parse_subnet(subnet_s, f"network '{name}'")
        for other_name, other_net in nets_seen:
            if subnet.overlaps(other_net):
                raise TopologyError(f"network '{name}' subnet {subnet} overlaps with network '{other_name}' subnet {other_net}")
        gateway = str(net_raw.get("gateway", "")).strip()
        if gateway:
            _validate_ip(gateway, f"network '{name}' gateway", subnet)
        routes = copy.deepcopy(_as_list(net_raw.get("routes", []), f"network '{name}'.routes"))
        for ridx, route in enumerate(routes):
            if not isinstance(route, dict):
                raise TopologyError(f"network '{name}'.routes[{ridx}] must be a mapping")
            _validate_cidr(str(route.get("to", "")), f"network '{name}'.routes[{ridx}].to")
            via = str(route.get("via", "")).strip()
            if not via:
                raise TopologyError(f"network '{name}'.routes[{ridx}] is missing via")
            _validate_ip(via, f"network '{name}'.routes[{ridx}].via")

        networks[name] = {
            "name": name,
            "subnet": str(subnet),
            "prefixlen": subnet.prefixlen,
            "switch": sw,
            "gateway": gateway or None,
            "routes": routes,
            "description": net_raw.get("description"),
        }
        if "link" in net_raw:
            networks[name]["link"] = copy.deepcopy(net_raw["link"])
        switch_to_network[sw] = name
        nets_seen.append((name, subnet))

    return networks, switch_to_network


def _normalise_routers(raw: Any, networks: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    routers: List[Dict[str, Any]] = []
    router_names: Set[str] = set()
    used_ips: Dict[str, str] = {}

    for idx, raw_router in enumerate(_as_list(raw, "routers")):
        if not isinstance(raw_router, dict):
            raise TopologyError(f"routers[{idx}] must be a mapping")
        name = str(raw_router.get("name", "")).strip()
        if not name:
            raise TopologyError(f"routers[{idx}] is missing name")
        if name in router_names:
            raise TopologyError(f"duplicate router name: {name}")
        router_names.add(name)
        interfaces: List[Dict[str, Any]] = []
        ifnames: Set[str] = set()
        for iidx, iface in enumerate(_as_list(raw_router.get("interfaces", []), f"router '{name}'.interfaces")):
            if not isinstance(iface, dict):
                raise TopologyError(f"router '{name}'.interfaces[{iidx}] must be a mapping")
            net_name = str(iface.get("network", "")).strip()
            if net_name not in networks:
                raise TopologyError(f"router '{name}'.interfaces[{iidx}] references unknown network '{net_name}'")
            ip = str(iface.get("ip", "")).strip()
            if not ip:
                raise TopologyError(f"router '{name}'.interfaces[{iidx}] is missing ip")
            subnet = ipaddress.IPv4Network(networks[net_name]["subnet"], strict=False)
            _validate_ip(ip, f"router '{name}' interface '{net_name}'", subnet)
            if _strip_prefix(ip) in used_ips:
                raise TopologyError(f"duplicate router IP {ip}: {name} conflicts with {used_ips[_strip_prefix(ip)]}")
            used_ips[_strip_prefix(ip)] = name
            ifname = str(iface.get("ifname") or f"{name}-{net_name}")
            if len(ifname) > 15:
                raise TopologyError(f"router '{name}' interface name '{ifname}' exceeds Linux 15-character limit")
            if ifname in ifnames:
                raise TopologyError(f"router '{name}' has duplicate interface name '{ifname}'")
            ifnames.add(ifname)
            item = {
                "network": net_name,
                "ip": _strip_prefix(ip),
                "ip_cidr": f"{_strip_prefix(ip)}/{networks[net_name]['prefixlen']}",
                "ifname": ifname,
                "switch": networks[net_name]["switch"],
            }
            if "link" in iface:
                item["link"] = copy.deepcopy(iface["link"])
            elif "link" in networks[net_name]:
                item["link"] = copy.deepcopy(networks[net_name]["link"])
            interfaces.append(item)
        if len(interfaces) < 2:
            raise TopologyError(f"router '{name}' must have at least two interfaces")
        routes = copy.deepcopy(_as_list(raw_router.get("routes", []), f"router '{name}'.routes"))
        for ridx, route in enumerate(routes):
            if not isinstance(route, dict):
                raise TopologyError(f"router '{name}'.routes[{ridx}] must be a mapping")
            _validate_cidr(str(route.get("to", "")), f"router '{name}'.routes[{ridx}].to")
            via = str(route.get("via", "")).strip()
            if not via:
                raise TopologyError(f"router '{name}'.routes[{ridx}] is missing via")
            _validate_ip(via, f"router '{name}'.routes[{ridx}].via")
        routers.append({
            "name": name,
            "interfaces": interfaces,
            "routes": routes,
            "firewall": copy.deepcopy(raw_router.get("firewall", {})),
            "sysctl": copy.deepcopy(raw_router.get("sysctl", {})),
        })
    return routers


def _node_network_fields(raw_node: Dict[str, Any], owner: str, is_l3: bool, networks: Dict[str, Dict[str, Any]], switch_to_network: Dict[str, str], default_switch: str) -> Dict[str, Any]:
    """Resolve switch, network, IP prefix, gateway and routes for one node."""
    out: Dict[str, Any] = {}
    if not is_l3:
        out["switch"] = str(raw_node.get("switch", default_switch))
        return out

    net_name = raw_node.get("network")
    switch = raw_node.get("switch")
    if net_name:
        net_name = str(net_name)
        if net_name not in networks:
            raise TopologyError(f"{owner}: references unknown network '{net_name}'")
        inferred_switch = networks[net_name]["switch"]
        if switch and str(switch) != inferred_switch:
            raise TopologyError(f"{owner}: switch '{switch}' does not match network '{net_name}' switch '{inferred_switch}'")
        switch = inferred_switch
    elif switch:
        switch = str(switch)
        if switch not in switch_to_network:
            raise TopologyError(f"{owner}: L3 nodes must define 'network' or use a switch that maps to exactly one network")
        net_name = switch_to_network[switch]
    else:
        raise TopologyError(f"{owner}: L3 nodes must define 'network'")

    network = networks[str(net_name)]
    out.update({
        "network": str(net_name),
        "switch": str(switch),
        "gateway": raw_node.get("gateway", network.get("gateway")),
        "routes": copy.deepcopy(raw_node.get("routes", network.get("routes", []))),
    })
    return out


def _finalize_node_ip(node: Dict[str, Any], owner: str, is_l3: bool, subnet_l2: Optional[ipaddress.IPv4Network], networks: Dict[str, Dict[str, Any]]) -> None:
    ip = _strip_prefix(str(node.get("ip", "")))
    if not ip:
        raise TopologyError(f"{owner}: missing IP")
    if is_l3:
        net_name = node.get("network")
        if net_name not in networks:
            raise TopologyError(f"{owner}: missing/invalid network")
        net = ipaddress.IPv4Network(networks[net_name]["subnet"], strict=False)
        _validate_ip(ip, owner, net)
        node["ip"] = ip
        node["ip_cidr"] = f"{ip}/{net.prefixlen}"
        if node.get("gateway"):
            _validate_ip(str(node["gateway"]), f"{owner}.gateway", net)
        for ridx, route in enumerate(node.get("routes", [])):
            _validate_cidr(str(route.get("to", "")), f"{owner}.routes[{ridx}].to")
            _validate_ip(str(route.get("via", "")), f"{owner}.routes[{ridx}].via")
    else:
        _validate_ip(ip, owner, subnet_l2)
        node["ip"] = ip


def load(
    topology_path: str,
    time_override: Optional[int] = None,
    output_override: Optional[str] = None,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
    scale: Optional[Dict[str, int]] = None,
    brokers: Optional[int] = None,
) -> Dict[str, Any]:
    """Load, expand, and validate a topology file."""

    topology_path = os.path.abspath(topology_path)
    base_dir = os.path.dirname(topology_path)
    topo = _load_yaml(topology_path)

    raw_catalog = topo.get("catalog", "catalog.yaml")
    catalog_path = raw_catalog if os.path.isabs(str(raw_catalog)) else os.path.join(base_dir, str(raw_catalog))
    catalog_doc = _load_yaml(catalog_path)
    catalog = catalog_doc.get("profiles")
    if not isinstance(catalog, dict):
        raise TopologyError(f"catalog '{catalog_path}' must contain a 'profiles' mapping")

    exp = topo.get("experiment", {}) or {}
    if not isinstance(exp, dict):
        raise TopologyError("experiment must be a mapping")
    exp_time = _to_int(time_override if time_override is not None else exp.get("time", 60), "experiment.time", 1)
    output = str(output_override or exp.get("output", "capture.pcap"))
    dataset_dir = str(topo.get("dataset_dir", "devices/urban_observatory"))

    switches = _normalize_switches(topo.get("switches"))
    switch_set = set(switches)
    is_l3 = bool(topo.get("networks") or topo.get("routers") or str(topo.get("mode", "")).lower() == "l3")

    network_doc = topo.get("network", {}) or {}
    if not isinstance(network_doc, dict):
        raise TopologyError("network must be a mapping")

    subnet_net: Optional[ipaddress.IPv4Network] = None
    nat = None
    networks: Dict[str, Dict[str, Any]] = {}
    switch_to_network: Dict[str, str] = {}
    routers: List[Dict[str, Any]] = []

    if is_l3:
        networks, switch_to_network = _normalise_networks(topo.get("networks"), switch_set)
        routers = _normalise_routers(topo.get("routers"), networks)
        if network_doc.get("nat"):
            nat = copy.deepcopy(network_doc.get("nat"))
    else:
        subnet = str(network_doc.get("subnet", "10.0.0.0/24"))
        subnet_net = _parse_subnet(subnet, "network")
        nat = copy.deepcopy(network_doc.get("nat", {"name": "nat0", "ip": "10.0.0.254", "switch": switches[0]}))
        if not isinstance(nat, dict):
            raise TopologyError("network.nat must be a mapping")
        nat.setdefault("name", "nat0")
        nat.setdefault("ip", "10.0.0.254")
        nat.setdefault("switch", switches[0])

    capture = copy.deepcopy(topo.get("capture", {"points": [switches[0]], "bpf": "not port 6653"}))
    if not isinstance(capture, dict):
        raise TopologyError("capture must be a mapping")
    capture.setdefault("points", [switches[0]])
    capture.setdefault("bpf", "not port 6653")

    scale = dict(scale or {})
    include_set = _parse_filter(include)
    exclude_set = _parse_filter(exclude)

    services_raw = copy.deepcopy(_as_list(topo.get("services", []), "services"))
    profiles_raw = copy.deepcopy(_as_list(topo.get("profiles", []), "profiles"))

    if brokers is not None:
        broker_count = _to_int(brokers, "--brokers", 1)
        found = False
        for service in services_raw:
            if isinstance(service, dict) and service.get("kind") == "mqtt_broker":
                service["count"] = broker_count
                found = True
                break
        if not found:
            raise TopologyError("--brokers was provided, but no service with kind='mqtt_broker' exists")

    for service in services_raw:
        if not isinstance(service, dict):
            raise TopologyError("each services[] entry must be a mapping")
        key = service.get("name") or service.get("kind")
        if key in scale:
            service["count"] = _to_int(scale[key], f"scale.{key}", 1)

    for profile in profiles_raw:
        if not isinstance(profile, dict):
            raise TopologyError("each profiles[] entry must be a mapping")
        key = profile.get("name") or profile.get("name_prefix") or profile.get("template")
        if key in scale:
            profile["count"] = _to_int(scale[key], f"scale.{key}", 1)

    placeholders = {"time": exp_time, "dataset_dir": dataset_dir}
    pool = IPPool()
    if nat:
        pool.reserve(nat.get("ip"))
    for router in routers:
        for iface in router.get("interfaces", []):
            pool.reserve(iface.get("ip"))
    for service in services_raw:
        pool.reserve(service.get("ip"))
    for profile in profiles_raw:
        pool.reserve(profile.get("ip"))

    plan: Dict[str, Any] = {
        "mode": "l3" if is_l3 else "l2",
        "experiment": {"time": exp_time, "output": output},
        "dataset_dir": dataset_dir,
        "catalog": os.path.relpath(catalog_path, base_dir) if os.path.commonpath([base_dir, catalog_path]) == base_dir else catalog_path,
        "network": {},
        "switches": switches,
        "links": copy.deepcopy(_as_list(topo.get("links", []), "links")),
        "capture": capture,
        "services": [],
        "profiles": [],
        "warnings": [],
    }
    if is_l3:
        plan["networks"] = networks
        plan["routers"] = routers
        plan["network"].update({"mode": "l3", "nat": nat})
        if topo.get("security") is not None:
            plan["security"] = copy.deepcopy(topo.get("security"))
    else:
        plan["network"].update({"mode": "l2", "subnet": str(subnet_net), "nat": nat})

    # Expand infrastructure services and non-IoT endpoints.
    for idx, service in enumerate(services_raw):
        owner = service.get("name") or service.get("kind") or f"services[{idx}]"
        count = _to_int(service.get("count", 1), f"{owner}.count", 1)
        image = service.get("image")
        if not image:
            raise TopologyError(f"{owner}: service is missing required field 'image'")

        if service.get("ip") and count == 1:
            ips = [_strip_prefix(str(service["ip"]))]
        elif service.get("ip") and count > 1:
            ips = [_strip_prefix(str(service["ip"]))] + pool.allocate(service.get("ip_pool"), count - 1, owner=owner)
        else:
            ips = pool.allocate(service.get("ip_pool"), count, owner=owner)

        for i, ip in enumerate(ips):
            name = str(service.get("name") if count == 1 else f"{service.get('name', service.get('kind', 'service'))}_{i + 1}")
            net_fields = _node_network_fields(service, name, is_l3, networks, switch_to_network, switches[0])
            node: Dict[str, Any] = {
                "name": name,
                "kind": service.get("kind"),
                "image": str(image),
                "ip": ip,
                "privileged": bool(service.get("privileged", False)),
                "link_up": bool(service.get("link_up", False)),
                "boot": _subst(service.get("boot", []), placeholders),
                "boot_delay": _to_int(service.get("boot_delay", 0), f"{owner}.boot_delay", 0),
            }
            node.update(net_fields)
            if "env" in service:
                node["env"] = _subst(service.get("env", {}), placeholders)
            if "volumes" in service:
                node["volumes"] = _subst(service.get("volumes", []), placeholders)
            if "dcmd" in service:
                node["dcmd"] = service["dcmd"]
            if "start" in service:
                node["start"] = _subst(service.get("start"), placeholders)
            if "log" in service:
                node["log"] = _subst(service.get("log"), placeholders)
            _finalize_node_ip(node, name, is_l3, subnet_net, networks)
            plan["services"].append(node)

    broker_ip = _first_mqtt_broker_ip(plan["services"])
    service_ips = _service_ip_by_name(plan["services"])
    n_brokers = sum(1 for s in plan["services"] if s.get("kind") == "mqtt_broker")

    # Expand device profiles.
    for idx, profile in enumerate(profiles_raw):
        tname = profile.get("template")
        if not tname:
            raise TopologyError(f"profiles[{idx}] is missing required field 'template'")
        if tname not in catalog:
            raise TopologyError(f"profiles[{idx}] references unknown catalog template '{tname}'")
        tmpl = catalog[tname]
        if not isinstance(tmpl, dict):
            raise TopologyError(f"catalog template '{tname}' must be a mapping")

        domain = profile.get("domain", tmpl.get("domain", "unspecified"))
        selectors = {str(domain), str(tname)}
        if include_set and not (selectors & include_set):
            continue
        if exclude_set and (selectors & exclude_set):
            continue

        count = _to_int(profile.get("count", 1), f"{profile.get('name') or tname}.count", 1)
        owner = str(profile.get("name") or profile.get("name_prefix") or tname)

        if count == 1 and "count" not in profile:
            ip = _strip_prefix(str(profile["ip"])) if profile.get("ip") else pool.allocate(profile.get("ip_pool"), 1, owner=owner)[0] if profile.get("ip_pool") else None
            if not ip:
                raise TopologyError(f"{owner}: profile requires either 'ip' or 'ip_pool'")
            name = str(profile.get("name") or owner)
            instances = [(name, ip, copy.deepcopy(profile.get("env", {})))]
        else:
            vary = profile.get("vary")
            combos = _variant_combos(vary, owner) if vary else copy.deepcopy(tmpl.get("variants", []))
            if not isinstance(combos, list) or not combos:
                raise TopologyError(
                    f"{owner}: count={count} requires a diversity pool ('vary' in topology or 'variants' in catalog). "
                    "Device profiles are not silently cloned."
                )
            if count > len(combos):
                raise TopologyError(
                    f"{owner}: requested {count} distinct profiles, but the diversity pool supplies only {len(combos)}"
                )
            prefix = str(profile.get("name_prefix") or profile.get("name") or tname)
            ips = pool.allocate(profile.get("ip_pool"), count, owner=owner)
            instances = []
            for i in range(count):
                combo = combos[i]
                if not isinstance(combo, dict):
                    raise TopologyError(f"{owner}: diversity entry {i} must be a mapping")
                env_i = copy.deepcopy(profile.get("env", {}))
                env_i.update(combo)
                instances.append((f"{prefix}_{i + 1}", ips[i], env_i))

        for name, ip, env_over in instances:
            protocol = str(profile.get("protocol", tmpl.get("protocol", "mqtt")))
            env: Dict[str, Any] = copy.deepcopy(tmpl.get("env", {}))

            broker_name = profile.get("broker")
            if broker_name:
                if broker_name not in service_ips:
                    raise TopologyError(f"{name}: broker '{broker_name}' does not match any service name")
                env.setdefault("MQTT_BROKER_ADDR", service_ips[broker_name])
            elif protocol == "mqtt" and broker_ip:
                env.setdefault("MQTT_BROKER_ADDR", broker_ip)

            env.update(env_over)
            ph = dict(placeholders, name=name)
            image = profile.get("image", tmpl.get("image"))
            if not image:
                raise TopologyError(f"{name}: profile/template '{tname}' is missing image")
            start = profile.get("start", tmpl.get("start"))
            net_fields = _node_network_fields(profile, name, is_l3, networks, switch_to_network, switches[0])
            node: Dict[str, Any] = {
                "name": name,
                "template": str(tname),
                "domain": str(domain),
                "protocol": protocol,
                "image": str(image),
                "ip": str(ip),
                "privileged": bool(profile.get("privileged", tmpl.get("privileged", False))),
                "link_up": bool(profile.get("link_up", tmpl.get("link_up", False))),
                "volumes": _subst(profile.get("volumes", tmpl.get("volumes", [])), ph),
                "env": _subst(env, ph),
                "start": _subst(start, ph) if start else None,
                "log": _subst(profile.get("log", tmpl.get("log", "/tmp/${name}.log")), ph),
                "boot": _subst(profile.get("boot", tmpl.get("boot", [])), ph),
            }
            node.update(net_fields)
            if "dcmd" in profile:
                node["dcmd"] = profile["dcmd"]
            elif "dcmd" in tmpl:
                node["dcmd"] = tmpl["dcmd"]
            _finalize_node_ip(node, name, is_l3, subnet_net, networks)
            plan["profiles"].append(node)

    if n_brokers > 1:
        plan["warnings"].append(
            f"Multiple MQTT brokers are present; profiles without explicit 'broker' or MQTT_BROKER_ADDR default to {broker_ip}."
        )

    _validate(plan, subnet_net)
    return plan


def _validate_capture_point(point: str, plan: Dict[str, Any], switch_set: Set[str], router_map: Dict[str, Dict[str, Any]]) -> None:
    if point in switch_set:
        return
    if plan.get("mode") == "l3":
        if point in router_map:
            return
        if ":" in point:
            router_name, selector = point.split(":", 1)
            if router_name not in router_map:
                raise TopologyError(f"capture point '{point}' references unknown router '{router_name}'")
            ifaces = router_map[router_name].get("interfaces", [])
            if any(selector in (iface.get("network"), iface.get("ifname")) for iface in ifaces):
                return
            raise TopologyError(f"capture point '{point}' references unknown interface/network '{selector}' on router '{router_name}'")
    raise TopologyError(f"capture point '{point}' is not a declared switch/router/interface")


def _validate(plan: Dict[str, Any], subnet_l2: Optional[ipaddress.IPv4Network]) -> None:
    switch_set = set(plan["switches"])
    router_map = {r["name"]: r for r in plan.get("routers", [])}
    names: Dict[str, str] = {}
    ips: Dict[str, str] = {}

    if plan.get("mode") == "l2":
        nat = plan["network"].get("nat")
        if not nat or not nat.get("name") or not nat.get("ip"):
            raise TopologyError("network.nat requires name and ip")
        if nat.get("switch") not in switch_set:
            raise TopologyError(f"NAT references unknown switch '{nat.get('switch')}'")
        _validate_ip(str(nat["ip"]), "NAT", subnet_l2)
        ips[str(nat["ip"])] = str(nat["name"])
    else:
        for net_name, net in plan.get("networks", {}).items():
            if net.get("switch") not in switch_set:
                raise TopologyError(f"network '{net_name}' references unknown switch '{net.get('switch')}'")
        for router in plan.get("routers", []):
            if router["name"] in names:
                raise TopologyError(f"duplicate node/router name: {router['name']}")
            names[router["name"]] = "router"
            for iface in router.get("interfaces", []):
                ip = iface["ip"]
                if ip in ips:
                    raise TopologyError(f"duplicate IP {ip}: router {router['name']} conflicts with {ips[ip]}")
                ips[ip] = f"{router['name']}:{iface['network']}"

    for node in plan["services"] + plan["profiles"]:
        name = node.get("name")
        ip = node.get("ip")
        if not name:
            raise TopologyError("node without name")
        if not ip:
            raise TopologyError(f"{name}: missing IP")
        if name in names:
            raise TopologyError(f"duplicate node name: {name}")
        names[name] = str(ip)
        if ip in ips:
            raise TopologyError(f"duplicate IP {ip}: {name} conflicts with {ips[ip]}")
        ips[ip] = name
        if node.get("switch") not in switch_set:
            raise TopologyError(f"{name} references unknown switch '{node.get('switch')}'")

    for idx, link in enumerate(plan.get("links", [])):
        if not isinstance(link, dict):
            raise TopologyError(f"links[{idx}] must be a mapping")
        for endpoint in ("a", "b"):
            if link.get(endpoint) not in switch_set:
                raise TopologyError(f"links[{idx}].{endpoint} references unknown switch '{link.get(endpoint)}'")
        for numeric in ("bw", "loss", "max_queue_size"):
            if numeric in link:
                try:
                    float(link[numeric])
                except (TypeError, ValueError) as exc:
                    raise TopologyError(f"links[{idx}].{numeric} must be numeric") from exc

    for point in plan.get("capture", {}).get("points", []):
        _validate_capture_point(str(point), plan, switch_set, router_map)

    total_containers = len(plan["services"]) + len(plan["profiles"])
    if plan.get("mode") == "l2":
        total_containers += 1
    if total_containers > 120:
        plan["warnings"].append(
            f"{total_containers} containers planned. Verify RAM/CPU before launch, especially in VMs."
        )


def dump(plan: Dict[str, Any], path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True) if out.parent != Path(".") else None
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(plan, f, sort_keys=False, default_flow_style=False, allow_unicode=True, width=120)


def summary(plan: Dict[str, Any]) -> str:
    by_domain: Dict[str, int] = {}
    by_protocol: Dict[str, int] = {}
    for profile in plan["profiles"]:
        by_domain[profile.get("domain", "unspecified")] = by_domain.get(profile.get("domain", "unspecified"), 0) + 1
        by_protocol[profile.get("protocol", "unspecified")] = by_protocol.get(profile.get("protocol", "unspecified"), 0) + 1

    service_names = ", ".join(service["name"] for service in plan["services"]) or "none"
    lines = [
        f"Mode     : {plan.get('mode', 'l2').upper()}",
        f"Switches : {', '.join(plan['switches'])}",
    ]
    if plan.get("mode") == "l3":
        routers = ", ".join(router["name"] for router in plan.get("routers", [])) or "none"
        networks = ", ".join(f"{name}={net['subnet']}" for name, net in plan.get("networks", {}).items()) or "none"
        lines.extend([
            f"Routers  : {len(plan.get('routers', []))}  ({routers})",
            f"Networks : {networks}",
        ])
    lines.extend([
        f"Services : {len(plan['services'])}  ({service_names})",
        f"Profiles : {len(plan['profiles'])}" + ("  (+1 NAT)" if plan.get("mode") == "l2" else "") + f"  => {len(plan['services']) + len(plan['profiles']) + (1 if plan.get('mode') == 'l2' else 0)} containers",
        "By domain: " + (", ".join(f"{k}={v}" for k, v in sorted(by_domain.items())) or "none"),
        "Protocol : " + (", ".join(f"{k}={v}" for k, v in sorted(by_protocol.items())) or "none"),
        f"Capture  : {plan['capture'].get('points')}  bpf='{plan['capture'].get('bpf', '')}'",
    ])
    if plan.get("links"):
        lines.append(f"Links    : {len(plan['links'])} inter-switch")
    for warning in plan.get("warnings", []):
        lines.append(f"WARNING  : {warning}")
    return "\n".join(lines)


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate and expand an IoT-Zoo topology YAML file.")
    parser.add_argument("topology")
    parser.add_argument("--time", type=int)
    parser.add_argument("--dump")
    args = parser.parse_args()

    try:
        plan = load(args.topology, time_override=args.time)
        print(summary(plan))
        if args.dump:
            dump(plan, args.dump)
            print(f"\nEffective config written to {args.dump}")
        return 0
    except TopologyError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
