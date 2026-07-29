#!/usr/bin/env python3
"""
Validate IoT-Zoo L3 segmented topology PCAP outputs.

This script checks whether all expected capture points produced PCAPs, whether
those PCAPs contain packets, and whether MQTT/RTSP/domain-specific traffic is
visible at the expected observation points.

Dependencies:
  - Python 3.8+
  - tshark and/or capinfos installed in PATH

Examples:
  python3 scripts/validate_l3_pcaps.py --pcap-dir /tmp --prefix iot_zoo_l3
  python3 scripts/validate_l3_pcaps.py --pcap-dir /tmp --prefix iot_zoo_l3 --out-dir ./validation_l3
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


EXPECTED_CAPTURES = [
    "sw_infra",
    "sw_hospital",
    "sw_university",
    "sw_industrial",
    "sw_school",
    "sw_cctv",
    "sw_outdoor",
    "r_edge_external",
    "r_edge_infra",
    "r_field_infra",
    "r_field_hospital",
    "r_field_university",
    "r_field_industrial",
    "r_field_school",
    "r_field_cctv",
    "r_field_outdoor",
]

DOMAINS = {
    "external": "10.10.0.",
    "infra": "10.20.0.",
    "hospital": "10.30.1.",
    "university": "10.30.2.",
    "industrial": "10.30.3.",
    "school": "10.30.4.",
    "cctv": "10.30.5.",
    "outdoor": "10.30.6.",
}

LOCAL_BROKERS = {
    "hospital": "10.30.1.100",
    "university": "10.30.2.100",
    "industrial": "10.30.3.100",
    "school": "10.30.4.100",
    "cctv": "10.30.5.100",
    "outdoor": "10.30.6.100",
}

CORE_BROKER = "10.20.0.100"
RTSP_SERVER = "10.20.0.20"


@dataclass
class CaptureSummary:
    capture: str
    pcap: str
    exists: bool
    size_bytes: int = 0
    packets: int = 0
    tcp_packets: int = 0
    udp_packets: int = 0
    icmp_packets: int = 0
    arp_packets: int = 0
    mqtt_packets: int = 0
    mqtt_publish_packets: int = 0
    rtsp_packets: int = 0
    port_1883_packets: int = 0
    port_8554_packets: int = 0
    unique_src_ips: int = 0
    unique_dst_ips: int = 0
    domains_seen: str = ""
    status: str = "UNKNOWN"
    notes: str = ""


def run_cmd(cmd: List[str], timeout: int = 45) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""), "TIMEOUT"
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"


def which(name: str) -> bool:
    return shutil.which(name) is not None


def pcap_path(pcap_dir: Path, prefix: str, capture: str) -> Path:
    return pcap_dir / f"{prefix}_{capture}.pcap"


def tshark_count(pcap: Path, display_filter: Optional[str] = None) -> int:
    if not which("tshark"):
        return -1
    cmd = ["tshark", "-r", str(pcap)]
    if display_filter:
        cmd += ["-Y", display_filter]
    cmd += ["-T", "fields", "-e", "frame.number"]
    code, out, _ = run_cmd(cmd, timeout=120)
    if code != 0:
        return -1
    if not out:
        return 0
    return len(out.splitlines())



def tshark_filter_count(pcap: Path, display_filter: str) -> int:
    return tshark_count(pcap, display_filter)


def pcap_filter_rows(pcap: Path, display_filter: str, fields: List[str], max_rows: int = 100) -> List[Dict[str, str]]:
    if not which("tshark"):
        return []
    cmd = ["tshark", "-r", str(pcap), "-Y", display_filter, "-T", "fields"]
    for field in fields:
        cmd += ["-e", field]
    code, out, _ = run_cmd(cmd, timeout=180)
    if code != 0 or not out:
        return []
    rows = []
    for i, line in enumerate(out.splitlines()):
        if i >= max_rows:
            break
        vals = line.split("\t")
        vals += [""] * (len(fields) - len(vals))
        rows.append(dict(zip(fields, vals)))
    return rows


def capinfos_packets(pcap: Path) -> int:
    """Return packet count, handling capinfos human suffixes such as `14 k`.

    Some Wireshark/capinfos builds abbreviate large counts using SI suffixes.
    A naive integer regex would parse `14 k` as 14, which makes reports show
    fewer total packets than protocol-specific filters.
    """
    if which("capinfos"):
        code, out, _ = run_cmd(["capinfos", "-c", str(pcap)], timeout=30)
        if code == 0:
            m = re.search(r"Number of packets:\s+([0-9][0-9.,]*)\s*([kKmMgGtT]?)", out)
            if m:
                raw = m.group(1).replace(",", "")
                suffix = m.group(2).lower()
                try:
                    value = float(raw)
                    multiplier = {"": 1, "k": 1000, "m": 1000000, "g": 1000000000, "t": 1000000000000}.get(suffix, 1)
                    return int(value * multiplier)
                except ValueError:
                    pass
    return tshark_count(pcap)


def unique_ip_count(pcap: Path, field: str) -> int:
    if not which("tshark"):
        return -1
    code, out, _ = run_cmd(["tshark", "-r", str(pcap), "-Y", "ip", "-T", "fields", "-e", field], timeout=120)
    if code != 0 or not out:
        return 0 if code == 0 else -1
    return len(set(x.strip() for x in out.splitlines() if x.strip()))


def domains_seen(pcap: Path) -> List[str]:
    if not which("tshark"):
        return []
    code, out, _ = run_cmd(["tshark", "-r", str(pcap), "-Y", "ip", "-T", "fields", "-e", "ip.src", "-e", "ip.dst"], timeout=120)
    if code != 0 or not out:
        return []
    seen = set()
    for line in out.splitlines():
        for token in re.split(r"\s+", line.strip()):
            for name, prefix in DOMAINS.items():
                if token.startswith(prefix):
                    seen.add(name)
    return sorted(seen)


def extract_mqtt_topics(pcap: Path, capture: str, max_rows: int = 50000) -> List[Dict[str, str]]:
    if not which("tshark"):
        return []
    fields = ["frame.time_epoch", "ip.src", "ip.dst", "tcp.srcport", "tcp.dstport", "mqtt.msgtype", "mqtt.topic"]
    cmd = ["tshark", "-r", str(pcap), "-Y", "mqtt", "-T", "fields"]
    for f in fields:
        cmd += ["-e", f]
    code, out, _ = run_cmd(cmd, timeout=180)
    if code != 0 or not out:
        return []
    rows = []
    for i, line in enumerate(out.splitlines()):
        if i >= max_rows:
            break
        vals = line.split("\t")
        vals += [""] * (len(fields) - len(vals))
        rows.append({"capture": capture, **dict(zip(fields, vals))})
    return rows


def summarize_capture(pcap_dir: Path, prefix: str, capture: str) -> CaptureSummary:
    p = pcap_path(pcap_dir, prefix, capture)
    summary = CaptureSummary(capture=capture, pcap=str(p), exists=p.exists())
    if not p.exists():
        summary.status = "FAIL"
        summary.notes = "missing pcap"
        return summary

    summary.size_bytes = p.stat().st_size
    if summary.size_bytes == 0:
        summary.status = "FAIL"
        summary.notes = "empty pcap"
        return summary

    summary.packets = capinfos_packets(p)
    summary.tcp_packets = tshark_count(p, "tcp")
    summary.udp_packets = tshark_count(p, "udp")
    summary.icmp_packets = tshark_count(p, "icmp")
    summary.arp_packets = tshark_count(p, "arp")
    summary.mqtt_packets = tshark_count(p, "mqtt")
    summary.mqtt_publish_packets = tshark_count(p, "mqtt.msgtype == 3")
    summary.rtsp_packets = tshark_count(p, "rtsp")
    summary.port_1883_packets = tshark_count(p, "tcp.port == 1883")
    summary.port_8554_packets = tshark_count(p, "tcp.port == 8554")
    # If capinfos returned a human-abbreviated or otherwise inconsistent count,
    # fall back to tshark's exact frame count.
    derived_min = max(
        summary.tcp_packets, summary.udp_packets, summary.icmp_packets, summary.arp_packets,
        summary.mqtt_packets, summary.mqtt_publish_packets, summary.rtsp_packets,
        summary.port_1883_packets, summary.port_8554_packets,
    )
    if summary.packets >= 0 and derived_min > summary.packets and which("tshark"):
        exact_packets = tshark_count(p)
        if exact_packets >= derived_min:
            summary.packets = exact_packets

    summary.unique_src_ips = unique_ip_count(p, "ip.src")
    summary.unique_dst_ips = unique_ip_count(p, "ip.dst")
    summary.domains_seen = ";".join(domains_seen(p))

    notes = []
    if summary.packets <= 0:
        summary.status = "FAIL"
        notes.append("no packets decoded")
    else:
        summary.status = "OK"

    # Domain-level sanity expectations.
    if capture.startswith("sw_") or capture.startswith("r_field_"):
        for domain in ["hospital", "university", "industrial", "school", "cctv", "outdoor", "infra"]:
            if domain in capture:
                if domain not in summary.domains_seen.split(";"):
                    summary.status = "WARN" if summary.status == "OK" else summary.status
                    notes.append(f"expected domain '{domain}' not detected in ip.src/ip.dst")
                break

    # Protocol sanity checks for domain captures.
    if capture in {"sw_hospital", "sw_university", "sw_industrial", "sw_school", "sw_outdoor"}:
        if summary.port_1883_packets <= 0 and summary.mqtt_packets <= 0:
            summary.status = "WARN"
            notes.append("expected MQTT/1883 traffic in this IoT domain")
    if capture in {"sw_cctv", "r_field_cctv", "r_field_infra", "sw_infra"}:
        if summary.port_8554_packets <= 0 and summary.rtsp_packets <= 0:
            # CCTV should have RTSP; infra/r_field_infra may have it depending on timing and app status.
            if capture == "sw_cctv":
                summary.status = "WARN"
                notes.append("expected RTSP/8554 traffic in CCTV capture")

    summary.notes = "; ".join(notes)
    return summary


def check_tcpdump_logs(pcap_dir: Path, prefix: str, captures: Iterable[str]) -> List[Dict[str, str]]:
    rows = []
    for cap in captures:
        log = pcap_dir / f"{prefix}_tcpdump_{cap}.log"
        # Current IoT-Zoo naming uses iot_zoo_tcpdump_<capture>.log, without the l3 prefix.
        alt_log = pcap_dir / f"iot_zoo_tcpdump_{cap}.log"
        if not log.exists() and alt_log.exists():
            log = alt_log
        status = "OK"
        notes = ""
        if not log.exists():
            status = "WARN"
            notes = "missing tcpdump log"
        else:
            txt = log.read_text(errors="replace")
            lower = txt.lower()
            bad_terms = ["no such device", "permission denied", "cannot", "error", "failed"]
            found = [t for t in bad_terms if t in lower]
            if found:
                status = "WARN"
                notes = "possible tcpdump issue: " + ", ".join(found)
            elif "listening on" not in lower and "packets captured" not in lower:
                status = "WARN"
                notes = "log does not clearly show tcpdump listening/capture summary"
        rows.append({"capture": cap, "log": str(log), "status": status, "notes": notes})
    return rows


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        path.write_text("")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Validate IoT-Zoo L3 multi-point PCAP outputs.")
    ap.add_argument("--pcap-dir", default="/tmp", help="Directory containing PCAP/log files. Default: /tmp")
    ap.add_argument("--prefix", default="iot_zoo_l3", help="PCAP filename prefix. Default: iot_zoo_l3")
    ap.add_argument("--out-dir", default="./validation_l3", help="Directory for CSV/JSON validation reports.")
    ap.add_argument("--captures", nargs="*", default=EXPECTED_CAPTURES, help="Capture names to validate.")
    ap.add_argument("--strict", action="store_true", help="Return non-zero for WARN as well as FAIL.")
    ap.add_argument("--expect-ip", action="append", default=[], help="Require at least one packet involving this IP in any validated capture. Repeatable.")
    ap.add_argument("--expect-port", action="append", default=[], type=int, help="Require at least one TCP or UDP packet with this port in any validated capture. Repeatable.")
    ap.add_argument("--expect-flow", action="append", default=[], help="Require packets matching src,dst,port. Example: 10.10.0.60,10.20.0.100,1883. Repeatable.")
    args = ap.parse_args(argv)

    pcap_dir = Path(args.pcap_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tool_status = {
        "tshark": which("tshark"),
        "capinfos": which("capinfos"),
        "mergecap": which("mergecap"),
        "editcap": which("editcap"),
    }
    if not tool_status["tshark"]:
        print("WARNING: tshark not found. Install with: sudo apt-get install -y tshark", file=sys.stderr)

    summaries = [summarize_capture(pcap_dir, args.prefix, cap) for cap in args.captures]
    summary_rows = [asdict(s) for s in summaries]
    write_csv(out_dir / "pcap_summary.csv", summary_rows)
    write_json(out_dir / "pcap_summary.json", summary_rows)

    log_rows = check_tcpdump_logs(pcap_dir, args.prefix, args.captures)
    write_csv(out_dir / "tcpdump_log_summary.csv", log_rows)

    topic_rows: List[Dict[str, str]] = []
    for s in summaries:
        if s.exists and s.size_bytes > 0:
            topic_rows.extend(extract_mqtt_topics(Path(s.pcap), s.capture))
    if topic_rows:
        write_csv(out_dir / "mqtt_topics.csv", topic_rows)
    else:
        (out_dir / "mqtt_topics.csv").write_text("")

    # Human-readable report.
    ok = sum(1 for s in summaries if s.status == "OK")
    warn = sum(1 for s in summaries if s.status == "WARN")
    fail = sum(1 for s in summaries if s.status == "FAIL")
    total_packets = sum(max(0, s.packets) for s in summaries)
    total_mqtt = sum(max(0, s.mqtt_packets) for s in summaries)
    total_1883 = sum(max(0, s.port_1883_packets) for s in summaries)
    total_rtsp = sum(max(0, s.rtsp_packets) for s in summaries)
    total_8554 = sum(max(0, s.port_8554_packets) for s in summaries)

    expectation_rows: List[Dict[str, object]] = []
    expectation_failures = 0
    existing_pcaps = [Path(s.pcap) for s in summaries if s.exists and s.size_bytes > 0]

    def check_expectation(label: str, display_filter: str) -> int:
        count = 0
        for p in existing_pcaps:
            c = tshark_filter_count(p, display_filter)
            if c > 0:
                count += c
        status = "OK" if count > 0 else "FAIL"
        expectation_rows.append({"expectation": label, "filter": display_filter, "packets": count, "status": status})
        return 0 if count > 0 else 1

    for ip in args.expect_ip:
        expectation_failures += check_expectation(f"ip {ip}", f"ip.addr == {ip}")
    for port in args.expect_port:
        expectation_failures += check_expectation(f"port {port}", f"tcp.port == {port} or udp.port == {port}")
    for flow in args.expect_flow:
        parts = [x.strip() for x in flow.split(",")]
        if len(parts) != 3:
            expectation_rows.append({"expectation": flow, "filter": "", "packets": 0, "status": "FAIL: expected src,dst,port"})
            expectation_failures += 1
            continue
        src, dst, port = parts
        expectation_failures += check_expectation(
            f"flow {src}->{dst}:{port}",
            f"ip.src == {src} and ip.dst == {dst} and (tcp.port == {port} or udp.port == {port})",
        )
    write_csv(out_dir / "attack_expectations.csv", expectation_rows)

    lines = []
    lines.append("# IoT-Zoo L3 PCAP Validation Report")
    lines.append("")
    lines.append(f"PCAP directory: `{pcap_dir}`")
    lines.append(f"Prefix: `{args.prefix}`")
    lines.append(f"Tool status: {tool_status}")
    lines.append("")
    lines.append(f"Summary: OK={ok}, WARN={warn}, FAIL={fail}")
    lines.append(f"Total decoded packets across captures: {total_packets}")
    lines.append(f"MQTT packets: protocol={total_mqtt}, tcp.port==1883={total_1883}")
    lines.append(f"RTSP packets: protocol={total_rtsp}, tcp.port==8554={total_8554}")
    if expectation_rows:
        lines.append("")
        lines.append("## Attack/flow expectations")
        for row in expectation_rows:
            lines.append(f"- **{row['expectation']}**: {row['status']}; packets={row['packets']}; filter=`{row['filter']}`")
    lines.append("")
    lines.append("## Capture details")
    for s in summaries:
        lines.append(
            f"- **{s.capture}**: {s.status}; size={s.size_bytes} bytes; packets={s.packets}; "
            f"mqtt={s.mqtt_packets}/1883={s.port_1883_packets}; rtsp={s.rtsp_packets}/8554={s.port_8554_packets}; "
            f"domains={s.domains_seen or '-'}; notes={s.notes or '-'}"
        )
    lines.append("")
    lines.append("## Interpretation notes")
    lines.append("- Multiple PCAPs are expected in the L3 topology because each capture point represents a different observation point.")
    lines.append("- For ML, keep `capture_point` or `domain` as metadata. Do not blindly merge all observation points without handling duplicate packets.")
    lines.append("- Domain PCAPs are useful for non-IID/domain-specific datasets; router/interface PCAPs are useful for boundary/core visibility.")
    (out_dir / "VALIDATION_REPORT.md").write_text("\n".join(lines))

    print("Validation report written to:", out_dir)
    if expectation_rows:
        print(f"Attack expectations: failures={expectation_failures}")
    print(f"OK={ok}, WARN={warn}, FAIL={fail}, total_packets={total_packets}, mqtt={total_mqtt}/{total_1883}, rtsp={total_rtsp}/{total_8554}")

    if fail > 0 or expectation_failures > 0:
        return 2
    if args.strict and warn > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
