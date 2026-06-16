#!/usr/bin/env python3
"""Minimal IoT-Zoo demo scenario.

This script intentionally uses a small subset of the full topology so that new users
can validate the environment before restoring all datasets and running the full
experiment.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from mininet.log import info, setLogLevel
from mininet.net import Containernet
from mininet.node import Controller
from mininet.nodelib import NAT

PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_DATA = PROJECT_ROOT / "sample_data" / "urban_observatory"
BROKER_IP = "10.0.0.100"

DEMO_DEVICES = [
    {"name": "demo_co", "ip": "10.0.0.50", "var": "CO", "topic": "city/air/co"},
    {"name": "demo_no2", "ip": "10.0.0.51", "var": "NO2", "topic": "city/air/no2"},
    {"name": "demo_temp", "ip": "10.0.0.60", "var": "Internal Temperature", "topic": "building/internal/temp"},
]


def require_root() -> None:
    if os.geteuid() != 0:
        print("This experiment must be run with sudo/root privileges.", file=sys.stderr)
        sys.exit(1)


def require_sample_data() -> None:
    if not SAMPLE_DATA.exists() or not list(SAMPLE_DATA.rglob("*.csv")):
        print(f"Sample data not found in {SAMPLE_DATA}", file=sys.stderr)
        print("Run: ./scripts/prepare_demo_data.sh --duration 120 --clean", file=sys.stderr)
        sys.exit(1)


def docker_image_exists(image: str) -> bool:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def require_images() -> None:
    missing = [image for image in ["myzoo/mqtt_broker", "myzoo/urban_sensor"] if not docker_image_exists(image)]
    if missing:
        print("Missing Docker image(s): " + ", ".join(missing), file=sys.stderr)
        print("Run: ./scripts/build_images.sh --demo", file=sys.stderr)
        sys.exit(1)


def cleanup(net=None) -> None:
    if net is not None:
        try:
            net.stop()
        except Exception:
            pass
    subprocess.run(
        "docker rm -f $(docker ps -aq --filter name=mn) >/dev/null 2>&1",
        shell=True,
        check=False,
    )


def fix_checksum(node) -> None:
    node.cmd("ethtool -K eth0 tx off >/dev/null 2>&1 || true")
    node.cmd("ethtool -K nat0-eth0 tx off >/dev/null 2>&1 || true")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the minimal IoT-Zoo demo scenario.")
    parser.add_argument("-t", "--time", type=int, default=120, help="Experiment duration in seconds")
    parser.add_argument("-o", "--output", default="/tmp/iot_zoo_demo.pcap", help="PCAP output path")
    args = parser.parse_args()

    require_root()
    require_sample_data()
    require_images()

    output_path = os.path.abspath(args.output)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    setLogLevel("info")
    cleanup()

    net = None
    try:
        net = Containernet(controller=Controller)
        net.addController("c0")

        info("*** Creating minimal IoT-Zoo demo topology\n")
        s1 = net.addSwitch("s1")
        broker = net.addDocker("broker", ip=BROKER_IP, dimage="myzoo/mqtt_broker", dcmd="/bin/bash")
        net.addLink(broker, s1)

        nodes = [broker]
        for dev in DEMO_DEVICES:
            info(f"*** Adding {dev['name']} ({dev['ip']}) for {dev['var']}\n")
            node = net.addDocker(
                dev["name"],
                ip=dev["ip"],
                dimage="myzoo/urban_sensor",
                volumes=[f"{SAMPLE_DATA}:/data:ro"],
                environment={
                    "MQTT_BROKER_ADDR": BROKER_IP,
                    "TIME_SCALE": "600.0",
                    "TARGET_VARIABLE": dev["var"],
                    "MQTT_TOPIC_PUB": dev["topic"],
                },
                dcmd="/bin/bash",
            )
            nodes.append(node)
            net.addLink(node, s1)

        nat = net.addNAT(name="nat0", ip="10.0.0.254")
        net.addLink(nat, s1)

        info("*** Starting network\n")
        net.start()

        for node in nodes:
            node.cmd("ip route del default 2>/dev/null || true")
            node.cmd("ip route add default via 10.0.0.254")
            fix_checksum(node)
        fix_checksum(nat)

        info(f"*** Starting tcpdump: {output_path}\n")
        s1.cmd(f"tcpdump -i any -w {output_path} -U not port 6653 >/tmp/iot_zoo_demo_tcpdump.log 2>&1 & echo $! > /tmp/iot_zoo_demo_tcpdump.pid")

        info("*** Starting MQTT broker\n")
        broker.cmd("/usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf -d &")
        time.sleep(2)

        for node in nodes[1:]:
            node.cmd(f"python3 -u /urban_sensor.py >/tmp/{node.name}.log 2>&1 &")

        info(f"*** Running demo for {args.time}s\n")
        start = time.time()
        while time.time() - start < args.time:
            remaining = int(args.time - (time.time() - start))
            sys.stdout.write(f"\rTime remaining: {remaining}s   ")
            sys.stdout.flush()
            time.sleep(1)
        print()

        info("*** Stopping tcpdump\n")
        s1.cmd("if [ -f /tmp/iot_zoo_demo_tcpdump.pid ]; then kill -INT $(cat /tmp/iot_zoo_demo_tcpdump.pid) 2>/dev/null || true; fi")
        time.sleep(2)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        cleanup(net)
        info("*** Demo cleanup completed\n")


if __name__ == "__main__":
    main()
