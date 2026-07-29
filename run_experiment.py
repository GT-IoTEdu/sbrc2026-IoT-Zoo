#!/usr/bin/env python3
"""
IoT-Zoo full-topology orchestrator.

The full experiment is configuration-driven. By default, this script reads
`topology.yaml`, which reproduces the original single-switch IoT-Zoo topology.
Users can point `--topology` to another YAML file to customize switches, links,
services, device profiles, capture points, scaling, and, in L3 mode, routers,
subnets, gateways, routes and ACL presets.

Dry-run mode does not import Containernet/Mininet and can be used on any machine
with Python + PyYAML to validate and inspect the expanded topology.
"""

from __future__ import annotations

import argparse
import glob
import ipaddress
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

import topology_loader as loader

CURRENT_DIR = Path(__file__).resolve().parent
DEFAULT_TOPOLOGY = CURRENT_DIR / "topology.yaml"
DEFAULT_PCAP = "/tmp/iot_zoo_full.pcap"
BOOT_SETTLE_SECONDS = 3
BOOT_CMD_TIMEOUT_SECONDS = int(os.environ.get("IOTZOO_BOOT_TIMEOUT", "30"))
_INTERFACE_COUNTER = 0


def _next_ifname(prefix: str = "iz") -> str:
    """Return a globally unique Linux interface name with <=15 characters.

    Mininet/Containernet derives interface names from node names by default.
    Descriptive names such as sw_external-eth1 or benign_dashboard-eth0 exceed
    Linux IFNAMSIZ (15 visible chars). This helper assigns compact deterministic
    names for generated veth endpoints while keeping YAML node names readable.
    """
    global _INTERFACE_COUNTER
    _INTERFACE_COUNTER += 1
    clean = re.sub(r"[^A-Za-z0-9]", "", prefix)[:3] or "iz"
    return f"{clean}{_INTERFACE_COUNTER:05d}"[:15]


def log(message: str) -> None:
    print(message, flush=True)


def _run_boot_cmd(node: Any, cmd: str, label: str, timeout: Optional[int] = None) -> str:
    """Run a finite boot command inside a Mininet/Containernet node.

    Using node.cmd() directly can block forever when a YAML command contains a
    shell quoting problem, or when a service command accidentally runs in the
    foreground. node.popen()+communicate(timeout=...) fails fast and reports the
    offending node/command, which is safer for large L3 experiments.
    """
    timeout = timeout or BOOT_CMD_TIMEOUT_SECONDS
    proc = node.popen(["/bin/sh", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        try:
            out, err = proc.communicate(timeout=2)
        except Exception:
            out, err = b"", b""
        raise RuntimeError(
            f"Boot command timed out after {timeout}s on {label}: {cmd}\n"
            f"stdout={out.decode(errors='replace')}\n"
            f"stderr={err.decode(errors='replace')}"
        ) from exc

    stdout = out.decode(errors="replace") if isinstance(out, (bytes, bytearray)) else str(out or "")
    stderr = err.decode(errors="replace") if isinstance(err, (bytes, bytearray)) else str(err or "")
    if proc.returncode != 0:
        raise RuntimeError(
            f"Boot command failed on {label} with exit code {proc.returncode}: {cmd}\n"
            f"stdout={stdout}\n"
            f"stderr={stderr}"
        )
    return stdout + stderr


def _run_optional_cmd(node: Any, cmd: str, timeout: int = 5) -> Tuple[int, str, str]:
    """Run a diagnostic command and return (returncode, stdout, stderr)."""
    proc = node.popen(["/bin/sh", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate(timeout=2)
        return 124, out.decode(errors="replace"), err.decode(errors="replace")
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


def _mqtt_healthcheck(node: Any, host: str = "127.0.0.1", port: int = 1883, timeout: int = 4) -> Tuple[bool, str]:
    """Check if a broker accepts a minimal MQTT publish on localhost."""
    cmd = (
        f"timeout {int(timeout)} mosquitto_pub -h {shlex.quote(host)} -p {int(port)} "
        "-t __iotzoo_healthcheck__ -m ok >/tmp/iotzoo_mqtt_health.out 2>/tmp/iotzoo_mqtt_health.err"
    )
    rc, out, err = _run_optional_cmd(node, cmd, timeout=timeout + 2)
    if rc == 0:
        return True, ""
    diag = node.cmd("cat /tmp/iotzoo_mqtt_health.err 2>/dev/null || true; tail -n 80 /tmp/mosquitto*.log /tmp/mosquitto.stdout /tmp/mosquitto.stderr /mosquitto/log/mosquitto.log 2>/dev/null || true")
    return False, (out + err + diag).strip()


def _wait_mqtt(node: Any, attempts: int = 12, sleep_s: float = 1.0, host: str = "127.0.0.1", port: int = 1883) -> Tuple[bool, str]:
    """Wait for a broker to become ready before declaring failure.

    Mosquitto can daemonize before the listener is fully ready, mainly when
    bridge mode is enabled. This avoids false negatives that prematurely force
    a local-only fallback.
    """
    last_diag = ""
    for _ in range(max(1, int(attempts))):
        ok, diag = _mqtt_healthcheck(node, host=host, port=port, timeout=4)
        if ok:
            return True, ""
        last_diag = diag
        node.cmd(f"sleep {float(sleep_s)}")
    return False, last_diag


def _mqtt_generated_config_cmd(entry: Dict[str, Any], bridge: bool = True) -> str:
    """Generate a resilient Mosquitto config inside a broker container and start it.

    The YAML boot commands are still honored, but this generated restart is used
    as a health-check fallback. It avoids long shell one-liners, gives each
    bridge a unique connection/client id, and binds the listener explicitly to
    0.0.0.0 so local devices can connect reliably.
    """
    name = str(entry.get("name", "broker"))
    safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
    lines = [
        "persistence false",
        "log_dest file /tmp/mosquitto_iotzoo.log",
        "listener 1883 0.0.0.0",
        "allow_anonymous true",
    ]
    ip = str(entry.get("ip", ""))
    # Only field brokers bridge to broker_core. The core broker must remain local.
    if bridge and name != "broker_core" and ip.startswith("10.30."):
        lines += [
            f"connection bridge_to_core_{safe}",
            "address 10.20.0.100:1883",
            "try_private false",
            "notifications false",
            "start_type automatic",
            "restart_timeout 5",
            f"remote_clientid {safe}_bridge",
            "topic # out 0",
        ]
    heredoc = "\n".join(lines) + "\n"
    return (
        "if [ -f /tmp/mosquitto_iotzoo.pid ]; then kill $(cat /tmp/mosquitto_iotzoo.pid) 2>/dev/null || true; fi; "
        "pkill -x mosquitto 2>/dev/null || true; "
        "sleep 0.8; "
        "cat > /tmp/mosquitto_iotzoo.conf <<'EOF'\n"
        + heredoc
        + "EOF\n"
        "nohup /usr/sbin/mosquitto -c /tmp/mosquitto_iotzoo.conf -v > /tmp/mosquitto.stdout 2>/tmp/mosquitto.stderr & echo $! > /tmp/mosquitto_iotzoo.pid"
    )


def _verify_and_repair_mqtt_brokers(ordered: List[Tuple[Any, Dict[str, Any], bool]], info: Any) -> None:
    """Ensure every MQTT broker is listening before devices start.

    In large L3 runs a single broker process can silently fail after daemonizing,
    causing clients to see SYN/RST on tcp/1883. This guard detects that condition
    and restarts the broker with a generated robust configuration. If a bridge
    config still fails, it falls back to a local-only broker so at least the
    domain traffic is generated and captured.
    """
    brokers = [(node, entry) for node, entry, is_service in ordered if is_service and entry.get("kind") == "mqtt_broker"]
    if not brokers:
        return
    info("*** Verifying MQTT brokers\n")
    for node, entry in brokers:
        name = entry["name"]
        host = str(entry.get("ip") or "127.0.0.1")
        ok, diag = _wait_mqtt(node, attempts=18, sleep_s=0.8, host=host)
        if not ok and host != "127.0.0.1":
            # Fallback diagnostic: some containers accept localhost before their L3 address is ready.
            ok, diag = _wait_mqtt(node, attempts=6, sleep_s=0.5, host="127.0.0.1")
        if ok:
            info(f"***   broker {name}: OK\n")
            continue
        info(f"***   broker {name}: not responding after readiness wait; restarting generated bridge/local config\n")
        if diag:
            info(f"***   broker {name} diagnostic: {diag[:700]}\n")
        _run_boot_cmd(node, _mqtt_generated_config_cmd(entry, bridge=True), f"{name}-generated-bridge", timeout=10)
        ok, diag = _wait_mqtt(node, attempts=18, sleep_s=0.8, host=host)
        if not ok and host != "127.0.0.1":
            ok, diag = _wait_mqtt(node, attempts=6, sleep_s=0.5, host="127.0.0.1")
        if ok:
            info(f"***   broker {name}: OK after restart\n")
            continue
        if name != "broker_core":
            info(f"***   broker {name}: bridge restart failed; falling back to local-only broker\n")
            if diag:
                info(f"***   broker {name} diagnostic after bridge restart: {diag[:700]}\n")
            _run_boot_cmd(node, _mqtt_generated_config_cmd(entry, bridge=False), f"{name}-local-only", timeout=10)
            ok, diag = _wait_mqtt(node, attempts=18, sleep_s=0.8, host=host)
            if not ok and host != "127.0.0.1":
                ok, diag = _wait_mqtt(node, attempts=6, sleep_s=0.5, host="127.0.0.1")
        if not ok:
            raise RuntimeError(f"MQTT broker {name} is not listening on tcp/1883 after repair. Diagnostic:\n{diag}")
        info(f"***   broker {name}: OK after local-only fallback\n")


def _collect_node_logs(ordered: List[Tuple[Any, Dict[str, Any], bool]], base_path: str) -> None:
    """Export the tail of container logs before Mininet removes the containers."""
    outdir = Path(base_path)
    outdir.mkdir(parents=True, exist_ok=True)
    for node, entry, _is_service in ordered:
        name = _safe_label(entry.get("name", "node"))
        log_path = str(entry.get("log") or "")
        snippets = []
        if log_path and log_path not in ("/dev/null", "null"):
            snippets.append(f"### {log_path}\n" + node.cmd(f"tail -n 200 {shlex.quote(log_path)} 2>&1 || true"))
        # Common service logs useful for Mosquitto/MediaMTX diagnostics.
        snippets.append("### common service logs\n" + node.cmd("tail -n 160 /tmp/mosquitto*.log /tmp/mosquitto.stdout /tmp/mosquitto.stderr /mosquitto/log/mosquitto.log /tmp/rtsp_server.log 2>/dev/null || true"))
        text = "\n".join(s for s in snippets if s.strip())
        if text.strip():
            (outdir / f"{name}.log").write_text(text, encoding="utf-8", errors="replace")


def prepare_datasets(base_path: Union[str, os.PathLike]) -> None:
    """Extract .xz datasets to plain files when the extracted file is missing."""
    base = Path(base_path)
    log(f"*** Checking datasets in: {base}")
    if not base.exists():
        raise RuntimeError(f"Dataset path not found: {base}")

    xz_files = sorted(glob.glob(str(base / "**" / "*.xz"), recursive=True))
    pending = [Path(p) for p in xz_files if not Path(str(p)[:-3]).exists()]
    if not pending:
        log("*** OK: All compressed datasets are already extracted or not required.")
        return

    log(f"*** FOUND {len(pending)} compressed dataset(s) to extract.")
    for i, xz_path in enumerate(pending, 1):
        log(f"   [{i}/{len(pending)}] Validating {xz_path.name}...")
        test = subprocess.run(["xz", "-t", str(xz_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if test.returncode != 0:
            raise RuntimeError(
                f"Invalid XZ dataset: {xz_path}\n"
                f"xz output: {test.stderr.strip()}\n"
                "Fix or replace this file before running the full topology."
            )
        log(f"   [{i}/{len(pending)}] Extracting {xz_path.name}...")
        subprocess.run(["unxz", "-k", "-f", str(xz_path)], check=True)
    log("*** Dataset preparation completed.")


def _abs_volume(volume: str) -> str:
    """Make a Docker volume host path absolute relative to the project root."""
    parts = str(volume).split(":")
    if not parts:
        return str(volume)
    host = parts[0]
    if host and not os.path.isabs(host):
        parts[0] = str(CURRENT_DIR / host)
    return ":".join(parts)


def _safe_label(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_") or "capture"


def _capture_output_path(base: str, point: str, index: int, total: int) -> str:
    if total == 1:
        return os.path.abspath(base)
    stem, ext = os.path.splitext(os.path.abspath(base))
    ext = ext or ".pcap"
    return f"{stem}_{_safe_label(point)}{ext}"




def _switch_dpid(index: int) -> str:
    """Return a deterministic OpenFlow datapath ID for arbitrary switch names.

    Mininet/Containernet can derive a DPID automatically only from canonical
    names such as s1, s23, etc. The L3 institutional topology uses descriptive
    names such as sw_external and sw_hospital, so we must assign DPIDs
    explicitly.
    """
    return f"{index:016x}"


def _add_switches(net: Any, switch_names: List[str]) -> Dict[str, Any]:
    """Create switches with explicit DPIDs so descriptive names work reliably."""
    switches: Dict[str, Any] = {}
    for idx, name in enumerate(switch_names, 1):
        switches[name] = net.addSwitch(name, dpid=_switch_dpid(idx))
    return switches

def _link_params(source: Dict[str, Any]) -> Dict[str, Any]:
    return {k: source[k] for k in ("bw", "delay", "loss", "jitter", "max_queue_size") if k in source}


def _node_cmd(node: Any, cmd: str) -> str:
    return node.cmd(cmd)



def _capture_target(point: str, switches: Dict[str, Any], routers: Dict[str, Any], router_cfgs: Dict[str, Dict[str, Any]]) -> Tuple[Any, str, str]:
    """Return (node, interface, display_label) for a router/interface capture point.

    Switch captures are handled separately because Mininet/OVS switches do not
    run in isolated network namespaces. Capturing "any" on a switch object can
    produce identical captures for all switches. For switch capture points we
    capture the concrete OVS port interfaces recorded during link creation.
    """
    if point in routers:
        return routers[point], "any", point
    if ":" in point:
        router_name, selector = point.split(":", 1)
        if router_name not in routers:
            raise RuntimeError(f"Capture point {point!r} references unknown router {router_name!r}")
        for iface in router_cfgs[router_name].get("interfaces", []):
            if selector in (iface.get("network"), iface.get("ifname")):
                return routers[router_name], str(iface["ifname"]), point
        raise RuntimeError(f"Capture point {point!r} references an unknown interface/network")
    raise RuntimeError(f"Unsupported capture point: {point}")


def _start_tcpdump(node: Any, intf: str, out: str, pidfile: str, logfile: str, bpf: str, label: str) -> None:
    cmd = f"tcpdump -i {shlex.quote(intf)} -w {shlex.quote(out)} -U"
    if bpf.strip():
        cmd += " " + shlex.quote(bpf.strip())
    cmd += f" > {shlex.quote(logfile)} 2>&1 & echo $! > {shlex.quote(pidfile)}"
    log(f"*** Starting tcpdump on {label} ({intf}) -> {out}")
    node.cmd(cmd)


def _merge_capture_files(files: List[str], out: str) -> None:
    """Merge per-interface tcpdump files into one capture file.

    For switch captures we start one tcpdump per OVS port. This avoids the
    incorrect Mininet pattern of using '-i any' on a switch object. When multiple
    ports are captured, mergecap combines them and editcap removes exact duplicate
    frames when available.
    """
    valid = [f for f in files if os.path.exists(f) and os.path.getsize(f) > 24]
    if not valid:
        return
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    if len(valid) == 1:
        os.replace(valid[0], out)
    elif shutil.which("mergecap"):
        tmp_merged = out + ".merged"
        subprocess.run(["mergecap", "-w", tmp_merged] + valid, check=False)
        if os.path.exists(tmp_merged) and os.path.getsize(tmp_merged) > 24:
            os.replace(tmp_merged, out)
    else:
        # Fallback: keep the first usable interface capture if mergecap is absent.
        os.replace(valid[0], out)

    if os.path.exists(out) and shutil.which("editcap"):
        tmp_dedup = out + ".dedup"
        subprocess.run(["editcap", "-d", out, tmp_dedup], check=False)
        if os.path.exists(tmp_dedup) and os.path.getsize(tmp_dedup) > 24:
            os.replace(tmp_dedup, out)

    for f in valid:
        try:
            if os.path.exists(f) and os.path.abspath(f) != os.path.abspath(out):
                os.remove(f)
        except OSError:
            pass


def _start_captures(
    switches: Dict[str, Any],
    routers: Dict[str, Any],
    router_cfgs: Dict[str, Dict[str, Any]],
    switch_capture_ifaces: Dict[str, List[str]],
    capture: Dict[str, Any],
    pcap_path: str,
) -> List[Dict[str, Any]]:
    """Start tcpdump on configured switch ports/router interfaces.

    Return capture handles. Switch captures are recorded as multi-interface
    groups and merged when stopped.
    """
    points = [str(p) for p in (capture.get("points", []) or [])]
    bpf = str(capture.get("bpf", "") or "")
    running: List[Dict[str, Any]] = []
    for idx, point in enumerate(points):
        final_out = _capture_output_path(pcap_path, point, idx, len(points))
        safe = _safe_label(point)

        if point in switches:
            ifaces = list(dict.fromkeys(switch_capture_ifaces.get(point, [])))
            if not ifaces:
                log(f"WARNING: no concrete switch interfaces known for capture point {point}; skipping")
                continue
            group: Dict[str, Any] = {"kind": "multi", "label": point, "out": final_out, "items": []}
            for j, intf in enumerate(ifaces, 1):
                tmp_out = f"{os.path.splitext(final_out)[0]}__{_safe_label(intf)}.pcap"
                pidfile = f"/tmp/iot_zoo_tcpdump_{safe}_{j}.pid"
                logfile = f"/tmp/iot_zoo_tcpdump_{safe}_{j}.log"
                _start_tcpdump(switches[point], intf, tmp_out, pidfile, logfile, bpf, point)
                group["items"].append({"node": switches[point], "pidfile": pidfile, "pcap": tmp_out})
            running.append(group)
            continue

        node, intf, label = _capture_target(point, switches, routers, router_cfgs)
        pidfile = f"/tmp/iot_zoo_tcpdump_{safe}.pid"
        logfile = f"/tmp/iot_zoo_tcpdump_{safe}.log"
        _start_tcpdump(node, intf, final_out, pidfile, logfile, bpf, label)
        running.append({"kind": "single", "label": label, "out": final_out, "items": [{"node": node, "pidfile": pidfile, "pcap": final_out}]})
    return running


def _stop_captures(captures: List[Dict[str, Any]]) -> None:
    for cap in captures:
        for item in cap.get("items", []):
            node = item["node"]
            pidfile = item["pidfile"]
            node.cmd(
                f"if [ -f {shlex.quote(pidfile)} ]; then "
                f"kill -INT $(cat {shlex.quote(pidfile)}) 2>/dev/null || true; "
                f"rm -f {shlex.quote(pidfile)}; fi"
            )
    if captures:
        time.sleep(2)

    for cap in captures:
        if cap.get("kind") == "multi":
            _merge_capture_files([item["pcap"] for item in cap.get("items", [])], cap["out"])

def _cleanup_mininet_containers() -> None:
    os.system("docker rm -f $(docker ps -aq --filter name=mn) > /dev/null 2>&1")


def _route_cmd(route: Dict[str, Any]) -> str:
    to = str(route.get("to", "")).strip()
    via = str(route.get("via", "")).strip()
    if to.lower() == "default":
        return f"ip route replace default via {shlex.quote(via)}"
    return f"ip route replace {shlex.quote(to)} via {shlex.quote(via)}"


def _configure_node_routes(node: Any, entry: Dict[str, Any]) -> None:
    """Configure routes inside a Docker/Containernet node.

    Containernet containers may also keep Docker's own eth0 interface
    (for example 172.17.0.0/16).  The emulated interface is the short
    interface name assigned in _build_l3() (h000xx).  Route installation must
    therefore explicitly use that interface instead of relying on Linux to
    infer the device.  This is especially important for attack containers,
    because their image CMD is a plain shell and they should follow the same
    routing pattern as the IoT device containers.
    """
    intf = str(entry.get("_intf_name", "eth0"))
    ip_cidr = str(entry.get("ip_cidr", entry.get("ip", ""))).strip()

    node.cmd(f"ip link set {shlex.quote(intf)} up > /dev/null 2>&1 || true")

    # Re-assert the emulated address and connected route.  This is idempotent
    # and prevents the container's Docker eth0 route from being selected.
    try:
        iface = ipaddress.ip_interface(ip_cidr)
        ip_addr = str(iface.ip)
        subnet = str(iface.network)
        node.cmd(f"ip addr replace {shlex.quote(ip_cidr)} dev {shlex.quote(intf)} > /dev/null 2>&1 || true")
        node.cmd(f"ip route replace {shlex.quote(subnet)} dev {shlex.quote(intf)} src {shlex.quote(ip_addr)} > /dev/null 2>&1 || true")
    except ValueError:
        pass

    node.cmd("ip route del default 2>/dev/null || true")
    if entry.get("gateway"):
        # Use dev+onlink because Docker containers can have an additional eth0
        # interface.  Without this, `ip route add default via <gateway>` may
        # silently fail or choose the wrong path in some images.
        node.cmd(
            f"ip route replace default via {shlex.quote(str(entry['gateway']))} "
            f"dev {shlex.quote(intf)} onlink > /dev/null 2>&1 || true"
        )
    for route in entry.get("routes", []) or []:
        node.cmd(_route_cmd(route) + " > /dev/null 2>&1 || true")

    node.cmd(f"ethtool -K {shlex.quote(intf)} tx off rx off sg off tso off gso off gro off > /dev/null 2>&1 || true")


def _configure_router_routes(router_node: Any, router_cfg: Dict[str, Any]) -> None:
    router_node.cmd("sysctl -w net.ipv4.ip_forward=1 > /dev/null")
    for iface in router_cfg.get("interfaces", []):
        ifname = iface["ifname"]
        router_node.cmd(f"ip link set {shlex.quote(ifname)} up")
        router_node.cmd(f"ethtool -K {shlex.quote(ifname)} tx off rx off sg off tso off gso off gro off > /dev/null 2>&1 || true")
    for key, value in (router_cfg.get("sysctl", {}) or {}).items():
        router_node.cmd(f"sysctl -w {shlex.quote(str(key))}={shlex.quote(str(value))} > /dev/null 2>&1 || true")
    for route in router_cfg.get("routes", []) or []:
        router_node.cmd(_route_cmd(route))


def _iptables_allow_rule(rule: Dict[str, Any]) -> str:
    cmd = "iptables -A FORWARD"
    if rule.get("src"):
        cmd += f" -s {shlex.quote(str(rule['src']))}"
    if rule.get("dst"):
        cmd += f" -d {shlex.quote(str(rule['dst']))}"
    if rule.get("proto"):
        cmd += f" -p {shlex.quote(str(rule['proto']))}"
    if rule.get("dport"):
        cmd += f" --dport {shlex.quote(str(rule['dport']))}"
    if rule.get("sport"):
        cmd += f" --sport {shlex.quote(str(rule['sport']))}"
    cmd += " -j ACCEPT"
    return cmd


def _configure_router_firewall(router_node: Any, router_cfg: Dict[str, Any]) -> None:
    firewall = router_cfg.get("firewall", {}) or {}
    preset = str(firewall.get("preset", "open")).strip().lower()

    router_node.cmd("iptables -F 2>/dev/null || true")
    router_node.cmd("iptables -t nat -F 2>/dev/null || true")
    router_node.cmd("iptables -P FORWARD ACCEPT 2>/dev/null || true")

    if preset in ("", "open", "none"):
        return

    # Conservative default: explicitly allowed flows only, plus established return traffic.
    router_node.cmd("iptables -P FORWARD DROP 2>/dev/null || true")
    router_node.cmd("iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || true")

    if preset == "edge_restricted":
        # External human clients may reach core services. Attack/scanner nodes remain blocked by default,
        # unless explicit YAML allow rules are added.
        default_rules = [
            {"src": "10.10.0.30/32", "dst": "10.20.0.100/32", "proto": "tcp", "dport": 1883},
            {"src": "10.10.0.40/32", "dst": "10.20.0.100/32", "proto": "tcp", "dport": 1883},
            {"src": "10.10.0.50/32", "dst": "10.20.0.100/32", "proto": "tcp", "dport": 1883},
            {"src": "10.20.0.0/24", "dst": "10.10.0.0/24"},
            {"src": "10.30.0.0/16", "dst": "10.10.0.0/24"},
        ]
    elif preset == "field_microsegmentation":
        # North-south communication is allowed between field domains and infrastructure.
        # East-west communication between 10.30.x.0/24 field domains is denied by the default DROP policy.
        default_rules = [
            {"src": "10.30.0.0/16", "dst": "10.20.0.0/24"},
            {"src": "10.20.0.0/24", "dst": "10.30.0.0/16"},
        ]
    else:
        default_rules = []

    for rule in default_rules + list(firewall.get("allow", []) or []):
        router_node.cmd(_iptables_allow_rule(rule) + " 2>/dev/null || true")

    for rule in firewall.get("drop", []) or []:
        cmd = _iptables_allow_rule(rule).replace(" -j ACCEPT", " -j DROP")
        router_node.cmd(cmd + " 2>/dev/null || true")

    if firewall.get("nat"):
        nat_cfg = firewall["nat"]
        out_if = nat_cfg.get("out_if")
        src = nat_cfg.get("src")
        if out_if and src:
            router_node.cmd(
                f"iptables -t nat -A POSTROUTING -s {shlex.quote(str(src))} -o {shlex.quote(str(out_if))} -j MASQUERADE 2>/dev/null || true"
            )


def _add_docker(net: Any, entry: Dict[str, Any]) -> Any:
    kwargs: Dict[str, Any] = {"ip": entry.get("ip_cidr", entry["ip"]), "dimage": entry["image"]}
    if entry.get("privileged"):
        kwargs["privileged"] = True
    if entry.get("volumes"):
        kwargs["volumes"] = [_abs_volume(v) for v in entry["volumes"]]
    if entry.get("env"):
        kwargs["environment"] = entry["env"]
    # Explicit YAML null means do not pass dcmd and allow the Docker image CMD.
    if "dcmd" in entry and entry["dcmd"] is not None:
        kwargs["dcmd"] = entry["dcmd"]
    return net.addDocker(entry["name"], **kwargs)


def _build_l2(plan: Dict[str, Any], net: Any, TCLink: Any, info: Any) -> Tuple[Dict[str, Any], Dict[str, Any], List[Tuple[Any, Dict[str, Any], bool]]]:
    switches = _add_switches(net, plan["switches"])
    routers: Dict[str, Any] = {}
    ordered: List[Tuple[Any, Dict[str, Any], bool]] = []

    for service in plan["services"]:
        info(f"*** Service {service['name']} ({service['ip']}) [{service.get('kind')}]\n")
        ordered.append((_add_docker(net, service), service, True))
    for profile in plan["profiles"]:
        info(f"*** Profile {profile['name']} ({profile['ip']}) -> {profile.get('template')}\n")
        ordered.append((_add_docker(net, profile), profile, False))

    for node, entry, _ in ordered:
        net.addLink(node, switches[entry["switch"]])

    for link in plan.get("links", []):
        params = _link_params(link)
        if params:
            net.addLink(switches[link["a"]], switches[link["b"]], cls=TCLink, **params)
        else:
            net.addLink(switches[link["a"]], switches[link["b"]])

    nat_cfg = plan["network"]["nat"]
    nat = net.addNAT(name=nat_cfg["name"], ip=nat_cfg["ip"])
    net.addLink(nat, switches[nat_cfg.get("switch", plan["switches"][0])])
    routers[nat_cfg["name"]] = nat
    return switches, routers, ordered


def _build_l3(plan: Dict[str, Any], net: Any, TCLink: Any, info: Any) -> Tuple[Dict[str, Any], Dict[str, Any], List[Tuple[Any, Dict[str, Any], bool]], Dict[str, List[str]]]:
    switches = _add_switches(net, plan["switches"])
    routers: Dict[str, Any] = {}
    ordered: List[Tuple[Any, Dict[str, Any], bool]] = []
    switch_capture_ifaces: Dict[str, List[str]] = {name: [] for name in plan["switches"]}

    info("*** Adding L3 routers\n")
    for router_cfg in plan.get("routers", []):
        routers[router_cfg["name"]] = net.addHost(router_cfg["name"], ip=None)

    info("*** Linking routers to L2 access switches\n")
    for router_cfg in plan.get("routers", []):
        router = routers[router_cfg["name"]]
        for iface in router_cfg.get("interfaces", []):
            params = _link_params(iface.get("link", {}))
            sw_intf = _next_ifname("sw")
            common = {
                "intfName1": iface["ifname"],
                "intfName2": sw_intf,
                "params1": {"ip": iface["ip_cidr"]},
            }
            switch_capture_ifaces.setdefault(iface["switch"], []).append(sw_intf)
            if params:
                net.addLink(router, switches[iface["switch"]], cls=TCLink, **common, **params)
            else:
                net.addLink(router, switches[iface["switch"]], **common)

    for service in plan["services"]:
        info(f"*** Service {service['name']} ({service['ip']}) [{service.get('kind')}] network={service.get('network')}\n")
        ordered.append((_add_docker(net, service), service, True))
    for profile in plan["profiles"]:
        info(f"*** Profile {profile['name']} ({profile['ip']}) -> {profile.get('template')} network={profile.get('network')}\n")
        ordered.append((_add_docker(net, profile), profile, False))

    for node, entry, _ in ordered:
        node_intf = _next_ifname("h")
        switch_intf = _next_ifname("sw")
        entry["_intf_name"] = node_intf
        switch_capture_ifaces.setdefault(entry["switch"], []).append(switch_intf)
        net.addLink(
            node,
            switches[entry["switch"]],
            intfName1=node_intf,
            intfName2=switch_intf,
            params1={"ip": entry.get("ip_cidr", entry["ip"])},
        )

    # Optional switch-switch links are still supported, but L3 topologies usually do not need them.
    for link in plan.get("links", []):
        params = _link_params(link)
        a_intf = _next_ifname("sw")
        b_intf = _next_ifname("sw")
        common = {"intfName1": a_intf, "intfName2": b_intf}
        switch_capture_ifaces.setdefault(link["a"], []).append(a_intf)
        switch_capture_ifaces.setdefault(link["b"], []).append(b_intf)
        if params:
            net.addLink(switches[link["a"]], switches[link["b"]], cls=TCLink, **common, **params)
        else:
            net.addLink(switches[link["a"]], switches[link["b"]], **common)

    return switches, routers, ordered, switch_capture_ifaces


def build_and_run(plan: Dict[str, Any]) -> None:
    # Lazy imports keep --dry-run usable without Containernet installed.
    # Import order matters for some Containernet/Mininet versions.
    from mininet.log import info, setLogLevel
    from mininet.net import Containernet
    from mininet.node import Controller
    from mininet.link import TCLink

    setLogLevel("info")
    pcap_path = os.path.abspath(plan["experiment"]["output"])

    _cleanup_mininet_containers()
    net = Containernet(controller=Controller)
    net.addController("c0")
    captures: List[Dict[str, Any]] = []
    ordered: List[Tuple[Any, Dict[str, Any], bool]] = []

    try:
        info("*** Initiating IoT-Zoo Experiment\n")
        if plan.get("mode") == "l3":
            switches, routers, ordered, switch_capture_ifaces = _build_l3(plan, net, TCLink, info)
        else:
            switches, routers, ordered = _build_l2(plan, net, TCLink, info)
            switch_capture_ifaces = {}

        info("*** Starting Network...\n")
        net.start()

        router_cfgs = {router["name"]: router for router in plan.get("routers", [])}

        if plan.get("mode") == "l3":
            info("*** Configuring L3 routers, routes and ACLs\n")
            for router_name, router_cfg in router_cfgs.items():
                _configure_router_routes(routers[router_name], router_cfg)
            for router_name, router_cfg in router_cfgs.items():
                _configure_router_firewall(routers[router_name], router_cfg)
        else:
            nat_cfg = plan["network"]["nat"]
            routers[nat_cfg["name"]].cmd("ethtool -K nat0-eth0 tx off > /dev/null 2>&1 || true")

        info("*** Configuring host routes\n")
        for node, entry, _is_service in ordered:
            if plan.get("mode") == "l3":
                _configure_node_routes(node, entry)
            else:
                nat_cfg = plan["network"]["nat"]
                node.cmd("ip route del default 2> /dev/null || true")
                node.cmd(f"ip route add default via {nat_cfg['ip']}")
                node.cmd("ethtool -K eth0 tx off > /dev/null 2>&1 || true")

        captures = _start_captures(switches, routers, router_cfgs, switch_capture_ifaces, plan.get("capture", {}), pcap_path)

        info("*** Booting services...\n")
        for node, entry, is_service in ordered:
            if is_service and entry.get("kind") == "mqtt_broker":
                for cmd in entry.get("boot", []):
                    info(f"***   boot {entry['name']}\n")
                    # Broker startup follows the original IoT-Zoo behavior.
                    # In Containernet, long-lived daemons started through node.popen()
                    # may be terminated when the helper shell exits. node.cmd() is
                    # therefore preferred here for Mosquitto, while finite boot
                    # commands for other services still use the timeout wrapper.
                    node.cmd(cmd)

        # Do not repair/replace broker processes here. The YAML boot commands
        # define broker behavior; logs are exported at shutdown for diagnosis.

        for node, entry, _ in ordered:
            if entry.get("link_up"):
                intf = str(entry.get("_intf_name", f"{entry['name']}-eth0"))
                node.cmd(f"ip link set {shlex.quote(intf)} up > /dev/null 2>&1 || true")
        time.sleep(BOOT_SETTLE_SECONDS)

        max_delay = 0
        for node, entry, is_service in ordered:
            if is_service and entry.get("kind") != "mqtt_broker":
                for cmd in entry.get("boot", []):
                    info(f"***   boot {entry['name']}\n")
                    _run_boot_cmd(node, cmd, entry["name"])
                max_delay = max(max_delay, int(entry.get("boot_delay", 0)))
        if max_delay:
            time.sleep(max_delay)

        info("*** Starting service clients and device clients...\n")
        for node, entry, is_service in ordered:
            # Services may also have start commands, e.g., benign external clients.
            if not is_service:
                for cmd in entry.get("boot", []):
                    node.cmd(cmd)
            start = entry.get("start")
            if start:
                # Re-apply L3 route setup immediately before long-running clients
                # and attack processes start.  This keeps attack containers aligned
                # with regular IoT device containers even when Docker's default eth0
                # interface is also present.
                if plan.get("mode") == "l3":
                    _configure_node_routes(node, entry)
                log_path = entry.get("log", "/dev/null")
                if log_path and log_path not in ("/dev/null", "null"):
                    log_dir = os.path.dirname(str(log_path)) or "/tmp"
                    node.cmd(f"mkdir -p {shlex.quote(log_dir)} 2>/dev/null || true")
                # Run the whole start expression in one background shell.
                # Important: do not append redirection directly to `start`, because
                # commands such as `sleep ...; attack; echo ... > log &` would only
                # redirect/background the final command. This made attack containers
                # appear to finish without producing traffic/logs.
                quoted_start = shlex.quote(str(start))
                quoted_log = shlex.quote(str(log_path))
                pidfile = f"/tmp/iotzoo_start_{_safe_label(entry.get('name', 'node'))}.pid"
                node.cmd(f"/bin/sh -lc {quoted_start} > {quoted_log} 2>&1 & echo $! > {shlex.quote(pidfile)}")

        duration = int(plan["experiment"]["time"])
        info(f"*** Running simulation for {duration}s...\n")
        started = time.time()
        while (time.time() - started) < duration:
            remaining = int(duration - (time.time() - started))
            sys.stdout.write(f"\rTime remaining: {remaining}s    ")
            sys.stdout.flush()
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        info("\n*** Finishing experiment...\n")
        try:
            _stop_captures(captures)
            if ordered:
                _collect_node_logs(ordered, "/tmp/iot_zoo_l3_logs")
        finally:
            try:
                net.stop()
            finally:
                _cleanup_mininet_containers()
                info("*** Cleaning completed.\n")



def _load_yaml_file(path: Union[str, os.PathLike]) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise loader.TopologyError(f"YAML file must contain a mapping: {path}")
    return data


def _plan_services_by_name(plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    services = {str(s["name"]): s for s in plan.get("services", [])}
    profiles = {str(p["name"]): p for p in plan.get("profiles", [])}
    return {**services, **profiles}


def _used_ips(plan: Dict[str, Any]) -> set:
    used = set()
    for section in ("services", "profiles"):
        for entry in plan.get(section, []) or []:
            if entry.get("ip"):
                used.add(str(entry["ip"]))
    for router in plan.get("routers", []) or []:
        for iface in router.get("interfaces", []) or []:
            if iface.get("ip"):
                used.add(str(iface["ip"]))
    return used


def _resolve_ip_or_name(plan: Dict[str, Any], value: Any) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    by_name = _plan_services_by_name(plan)
    if raw in by_name:
        return str(by_name[raw]["ip"])
    return raw


def _resolve_target_list(plan: Dict[str, Any], values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [v for v in re.split(r"[,\s]+", values) if v]
    if not isinstance(values, list):
        raise loader.TopologyError(f"targets must be a list or string, got {values!r}")
    return [_resolve_ip_or_name(plan, v) for v in values]


def _allocate_attack_ip(plan: Dict[str, Any], network_name: str, preferred: Optional[str] = None, start_ip: Optional[str] = None) -> str:
    if network_name not in plan.get("networks", {}):
        raise loader.TopologyError(f"attack network {network_name!r} not found in topology")
    net_cfg = plan["networks"][network_name]
    subnet = ipaddress.ip_network(str(net_cfg["subnet"]), strict=False)
    used = _used_ips(plan)
    if preferred:
        ip = ipaddress.ip_address(str(preferred))
        if ip not in subnet:
            raise loader.TopologyError(f"attack IP {preferred} is outside network {network_name} ({subnet})")
        if str(ip) in used:
            raise loader.TopologyError(f"attack IP {preferred} is already used in the topology")
        return str(ip)
    start = ipaddress.ip_address(start_ip) if start_ip else None
    for ip in subnet.hosts():
        if start and ip < start:
            continue
        s_ip = str(ip)
        if s_ip not in used:
            return s_ip
    raise loader.TopologyError(f"no free IP address available in network {network_name}")


def _env_key(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", str(key)).upper()


def _env_value(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(v) for v in value)
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _attack_command(entry: Dict[str, Any], args: List[str], env: Dict[str, Any], start_s: int, duration_s: int) -> str:
    env_map = {str(k): _env_value(v) for k, v in env.items() if v is not None}
    env_parts = " ".join(f"{_env_key(k)}={shlex.quote(v)}" for k, v in sorted(env_map.items()))
    arg_parts = " ".join(shlex.quote(str(a)) for a in args if a is not None and str(a) != "")
    timeout_s = max(1, int(duration_s) + 5)
    start_delay = max(0, int(start_s))
    # Diagnostics run inside the attack container. They make route/image issues
    # visible in /tmp/iot_zoo_l3_logs/<attack>.log instead of silently producing
    # an empty attack trace.
    diag = (
        "echo '[attack] network diagnostics'; "
        "(ip -4 addr show 2>&1 || true); "
        "(ip route show 2>&1 || true); "
    )
    prefix = f"sleep {start_delay}; echo '[attack] starting {entry['name']} type={entry['attack_type']}'; " + diag
    command = f"env {env_parts} timeout {timeout_s} /iotzoo_attack/entrypoint.sh {arg_parts}"
    return prefix + command + f"; rc=$?; echo '[attack] finished {entry['name']} rc='${{rc}}; exit $rc"


def _append_attack_firewall_rule(plan: Dict[str, Any], src_ip: str, target_ip: str, proto: str, port: Optional[int]) -> None:
    if plan.get("mode") != "l3":
        return
    for router in plan.get("routers", []) or []:
        if router.get("name") != "r_edge":
            continue
        firewall = router.setdefault("firewall", {})
        allow = firewall.setdefault("allow", [])
        rule: Dict[str, Any] = {"src": f"{src_ip}/32", "dst": f"{target_ip}/32"}
        if proto:
            rule["proto"] = proto
        if port and proto in {"tcp", "udp"}:
            rule["dport"] = int(port)
        if rule not in allow:
            allow.append(rule)


def apply_attack_scenarios(plan: Dict[str, Any], scenario_paths: Optional[List[str]]) -> Dict[str, Any]:
    """Inject attack containers from one or more attack-scenario YAML files.

    The benign topology stays unchanged. Each enabled attack becomes an extra
    service container connected to the requested network, with a delayed start
    command controlled by start_s/duration_s. This allows isolated and combined
    attacks without duplicating the full topology YAML.
    """
    if not scenario_paths:
        plan["attack_scenarios"] = []
        return plan

    catalog_path = CURRENT_DIR / "attacks" / "attack_catalog.yaml"
    catalog = _load_yaml_file(catalog_path)
    if not isinstance(catalog, dict) or not catalog:
        raise loader.TopologyError(f"attack catalog is empty or invalid: {catalog_path}")

    injected: List[Dict[str, Any]] = []
    for scenario_path in scenario_paths:
        scenario_file = Path(scenario_path)
        if not scenario_file.is_absolute():
            scenario_file = CURRENT_DIR / scenario_file
        scenario = _load_yaml_file(scenario_file)
        meta = scenario.get("scenario", {}) or {}
        attacks = scenario.get("attacks", []) or []
        if not isinstance(attacks, list):
            raise loader.TopologyError(f"attacks must be a list in {scenario_file}")
        ip_start = str(meta.get("ip_start", "10.10.0.60"))
        default_network = str(meta.get("default_network", "external"))
        for idx, attack in enumerate(attacks, 1):
            if not attack or not attack.get("enabled", True):
                continue
            attack_type = str(attack.get("type", "")).strip()
            if attack_type not in catalog:
                raise loader.TopologyError(f"unknown attack type {attack_type!r} in {scenario_file}")
            spec = catalog[attack_type]
            name = str(attack.get("name") or f"atk_{attack_type}_{idx}")
            existing_names = {e["name"] for e in plan.get("services", []) + plan.get("profiles", [])}
            if name in existing_names:
                raise loader.TopologyError(f"attack node name {name!r} already exists in topology")
            network_name = str(attack.get("network") or spec.get("default_network") or default_network)
            net_cfg = plan["networks"].get(network_name)
            if not net_cfg:
                raise loader.TopologyError(f"attack {name}: network {network_name!r} not found")
            ip = _allocate_attack_ip(plan, network_name, preferred=attack.get("ip"), start_ip=ip_start)

            # Resolve target(s).
            target_ip = str(attack.get("target_ip") or "")
            target = attack.get("target") or spec.get("default_target")
            if not target_ip and target:
                target_ip = _resolve_ip_or_name(plan, target)
            targets = attack.get("targets", spec.get("default_targets"))
            target_ips = _resolve_target_list(plan, targets)
            target_net = str(attack.get("target_net") or spec.get("default_target_net") or "")
            target_port = attack.get("target_port", spec.get("default_target_port"))
            target_port_int = int(target_port) if target_port not in (None, "") else None

            params = dict(spec.get("params", {}) or {})
            params.update(attack.get("params", {}) or {})
            start_s = int(attack.get("start_s", spec.get("default_start_s", 30)))
            duration_s = int(attack.get("duration_s", spec.get("default_duration_s", params.get("duration_s", 10))))
            params["duration_s"] = duration_s
            if target_port_int is not None:
                params["target_port"] = target_port_int
            if target_ip:
                params["target_ip"] = target_ip
            if target_ips:
                params["targets"] = " ".join(target_ips)
            if target_net:
                params["target_net"] = target_net
            if "ports" in params and isinstance(params["ports"], list):
                params["ports"] = ",".join(str(p) for p in params["ports"])

            args: List[str] = []
            for arg in spec.get("args", []) or []:
                if arg == "target_ip":
                    args.append(target_ip)
                elif arg == "target_port":
                    args.append(str(target_port_int or ""))
                elif arg == "targets":
                    args.append(" ".join(target_ips))
                elif arg == "target_net":
                    args.append(target_net)
                else:
                    args.append(str(params.get(arg, "")))

            entry: Dict[str, Any] = {
                "name": name,
                "kind": "attack",
                "attack_type": attack_type,
                "image": spec["image"],
                "ip": ip,
                "ip_cidr": f"{ip}/{net_cfg.get('prefixlen', 24)}",
                "network": network_name,
                "switch": net_cfg["switch"],
                "gateway": net_cfg.get("gateway"),
                "routes": list(net_cfg.get("routes", []) or []),
                "privileged": bool(attack.get("privileged", spec.get("privileged", False))),
                "link_up": True,
                "dcmd": "/bin/sh",
                "boot": [],
                "boot_delay": 0,
                "env": { _env_key(k): _env_value(v) for k, v in params.items() },
                "start": _attack_command({"name": name, "attack_type": attack_type}, args, params, start_s, duration_s),
                "log": f"/tmp/{name}.log",
                "_attack_meta": {
                    "scenario": str(meta.get("name") or scenario_file.stem),
                    "scenario_file": str(scenario_file),
                    "type": attack_type,
                    "target_ip": target_ip,
                    "target_port": target_port_int,
                    "target_net": target_net,
                    "targets": target_ips,
                    "start_s": start_s,
                    "duration_s": duration_s,
                },
            }
            plan.setdefault("services", []).append(entry)
            injected.append(entry)
            # Make successful external MQTT/recon/flood scenarios possible while retaining the baseline restricted edge.
            if bool(attack.get("allow_through_edge", spec.get("allow_through_edge", False))):
                if target_ip:
                    proto = "icmp" if attack_type == "icmp_flood" or attack_type == "ping_sweep" else ("udp" if attack_type in {"udp_flood", "port_scanner_udp"} else "tcp")
                    _append_attack_firewall_rule(plan, ip, target_ip, proto, target_port_int)
                for target_item in target_ips:
                    # For scans, allow configured ports to reduce firewall artifacts unless explicitly disabled.
                    ports = params.get("ports")
                    proto = "udp" if attack_type == "port_scanner_udp" else "tcp"
                    if isinstance(ports, str) and ports:
                        for p in str(ports).split(","):
                            try:
                                _append_attack_firewall_rule(plan, ip, target_item, proto, int(p))
                            except ValueError:
                                pass
                    else:
                        _append_attack_firewall_rule(plan, ip, target_item, proto, target_port_int)
                if target_net and attack_type == "ping_sweep":
                    # Keep this broad only for scenario-scoped attack nodes.
                    _append_attack_firewall_rule(plan, ip, target_net, "icmp", None)
        plan.setdefault("attack_scenarios", []).append({"file": str(scenario_file), "name": str(meta.get("name") or scenario_file.stem)})

    attack_rows = []
    for e in injected:
        row = dict(e.get("_attack_meta", {}) or {})
        row.update({"name": e["name"], "ip": e["ip"]})
        attack_rows.append(row)
    plan["attacks"] = attack_rows
    return plan


def attack_summary(plan: Dict[str, Any]) -> str:
    attacks = plan.get("attacks", []) or []
    if not attacks:
        return "Attacks  : none"
    parts = []
    for a in attacks:
        target = a.get("target_ip") or a.get("target_net") or ",".join(a.get("targets") or []) or "-"
        port = f":{a.get('target_port')}" if a.get("target_port") else ""
        parts.append(f"{a.get('name')}[{a.get('type')}] {a.get('ip')} -> {target}{port} @ {a.get('start_s')}s/{a.get('duration_s')}s")
    return "Attacks  : " + "; ".join(parts)


def parse_scale(values: Optional[List[str]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for value in values or []:
        if "=" not in value:
            raise loader.TopologyError(f"--scale expects name=N, got '{value}'")
        key, raw_n = value.split("=", 1)
        key = key.strip()
        if not key:
            raise loader.TopologyError(f"--scale expects a non-empty name, got '{value}'")
        try:
            out[key] = int(raw_n)
        except ValueError as exc:
            raise loader.TopologyError(f"--scale expects an integer count, got '{value}'") from exc
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or validate an IoT-Zoo configuration-driven topology.")
    parser.add_argument("-t", "--time", type=int, default=None, help="experiment duration in seconds")
    parser.add_argument("-o", "--output", default=None, help="PCAP output path")
    parser.add_argument("--topology", default=str(DEFAULT_TOPOLOGY), help="topology YAML file")
    parser.add_argument("--attack-scenario", action="append", help="attack scenario YAML file to layer on top of the benign topology; can be repeated")
    parser.add_argument("--include", action="append", help="domain/template to keep; comma-separated or repeated")
    parser.add_argument("--exclude", action="append", help="domain/template to drop; comma-separated or repeated")
    parser.add_argument("--scale", action="append", help="scale a service or diversity-backed profile: name=N")
    parser.add_argument("--brokers", type=int, help="number of MQTT broker service instances")
    parser.add_argument("--dump-config", help="write the expanded effective topology YAML")
    parser.add_argument("--dry-run", action="store_true", help="validate and expand only; do not launch Containernet")
    parser.add_argument("--no-prepare-data", action="store_true", help="skip host-side extraction of compressed datasets")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        plan = loader.load(
            args.topology,
            time_override=args.time,
            output_override=args.output or DEFAULT_PCAP,
            include=args.include,
            exclude=args.exclude,
            scale=parse_scale(args.scale),
            brokers=args.brokers,
        )
        apply_attack_scenarios(plan, args.attack_scenario)
        print(loader.summary(plan))
        print(attack_summary(plan))
        if args.dump_config:
            loader.dump(plan, args.dump_config)
            print(f"\n*** Effective config written to {args.dump_config}")
        if args.dry_run:
            print("\n*** Dry-run: no network launched.")
            return 0
        if not args.no_prepare_data:
            dataset_path = CURRENT_DIR / plan["dataset_dir"]
            prepare_datasets(dataset_path)
        build_and_run(plan)
        return 0
    except loader.TopologyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
