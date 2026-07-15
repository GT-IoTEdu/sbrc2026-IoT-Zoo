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
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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
    node.cmd("ip route del default 2>/dev/null || true")
    if entry.get("gateway"):
        node.cmd(f"ip route add default via {shlex.quote(str(entry['gateway']))}")
    for route in entry.get("routes", []) or []:
        node.cmd(_route_cmd(route))
    intf = str(entry.get("_intf_name", "eth0"))
    node.cmd(f"ip link set {shlex.quote(intf)} up > /dev/null 2>&1 || true")
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
                log_path = entry.get("log", "/dev/null")
                node.cmd(f"{start} > {log_path} 2>&1 &")

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
        print(loader.summary(plan))
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
