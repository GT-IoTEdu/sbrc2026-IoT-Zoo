#!/usr/bin/env python3
"""
# Dataset
    /dataset.csv.xz (LZMA/XZ)

# MQTT Topic
    elevator/predictive_maintenance/bearing_<bearing_id>

# Format
    "timestamp","ball_bearing","humidity","vibration"
    "2024-01-01 00:00:00","bearing_1","45.5","120.3"
"""

import csv
import json
import lzma
import os
import random
import shutil
import signal
import subprocess
import sys
import threading
import time

import paho.mqtt.publish as publish

config = {
    "MQTT_BROKER_ADDR": "localhost",
    "MQTT_TOPIC_PUB": "elevator/predictive_maintenance",
    "MQTT_AUTH": "",
    "MQTT_QOS": 0,
    "TLS": "",
    "TLS_INSECURE": "false",
    "SLEEP_TIME": 60,
    "SLEEP_TIME_SD": 5,
    "PING_SLEEP_TIME": 60,
    "PING_SLEEP_TIME_SD": 1,
    "ACTIVE_TIME": 60,
    "ACTIVE_TIME_SD": 0,
    "INACTIVE_TIME": 0,
    "INACTIVE_TIME_SD": 0,
    "NTP_SERVER": "localhost",
    "NTP_SLEEP_TIME": 60,
    "NTP_SLEEP_TIME_SD": 0,
}

def readloop(file, openfunc=open, skipfirst=True):
    with openfunc(file, "rt", encoding="utf-8") as f:
        while True:
            if skipfirst:
                f.readline()
            for line in f:
                yield line
            f.seek(0, 0)

def data2dict(colnames, data, units=None):
    if not units:
        units = [None for _ in range(len(colnames))]
    values = [{"value": v, "unit": u} if u else v for v, u in zip(data, units)]
    return dict(zip(colnames, values))

def as_json(payload):
    return json.dumps(payload)

def signal_handler(signum, stackframe, event):
    print(f"Handling signal {signum}")
    event.set()

def ping(bin_path, destination, attempts=3, wait=10):
    for i in range(attempts):
        result = subprocess.run([bin_path, "-c1", destination], capture_output=False, check=False)
        if result.returncode == 0 or i == attempts - 1:
            return result.returncode == 0
        time.sleep(wait)
    return result.returncode == 0

def broker_ping(sleep_t, sleep_t_sd, die_event, broker_addr, ping_bin):
    while not die_event.is_set():
        ping(ping_bin, broker_addr, attempts=1, wait=1)
        die_event.wait(timeout=max(0, random.gauss(sleep_t, sleep_t_sd)))

def _to_bool(v: str) -> bool:
    vv = (v or "").strip().strip('"').strip().casefold()
    if vv in ("1", "true", "t", "yes", "y", "on"):
        return True
    if vv in ("0", "false", "f", "no", "n", "off", ""):
        return False
    return True

def _sanitize_device(dev: str) -> str:
    d = (dev or "").strip().strip('"')
    return d.replace(":", "_")

def telemetry(
    sleep_t,
    sleep_t_sd,
    event,
    die_event,
    mqtt_topic,
    broker_addr,
    mqtt_auth,
    mqtt_qos,
    mqtt_tls,
    mqtt_cacert,
    mqtt_tls_insecure,
):
    print("[telemetry] starting thread")

    dataset_fname = "/dataset.csv.xz"
    dataset_sep = ","

    # Updated headers for elevator predictive maintenance
    headers = ["timestamp", "ball_bearing", "humidity", "vibration"]
    units = [None, None, "%", "Hz"]  # Adjust units as needed

    try:
        data_iter = readloop(dataset_fname, lzma.open)
        print(f"[telemetry] opened `{dataset_fname}'")
    except Exception as e:
        print(f"[telemetry] error opening `{dataset_fname}': {e}")
        die_event.set()
        return

    if mqtt_tls:
        tls_arg = {"ca_certs": mqtt_cacert, "insecure": mqtt_tls_insecure}
        port = 8883
    else:
        tls_arg = None
        port = 1883

    while not die_event.is_set():
        if event.is_set():
            try:
                raw_line = next(data_iter).strip()
                if not raw_line:
                    continue

                row = next(csv.reader([raw_line], delimiter=dataset_sep, quotechar='"'))
                if len(row) != len(headers):
                    raise ValueError(f"unexpected column count: got={len(row)} expected={len(headers)} line={raw_line!r}")

                # Parse data types based on your dataset structure
                # Adjust indices and conversion based on actual data format
                row[0] = row[0].strip()  # timestamp as string
                row[1] = row[1].strip()  # ball_bearing identifier
                row[2] = float(row[2])    # humidity
                row[3] = float(row[3])    # vibration

                ball_bearing = row[1]
                topic_device = f"{mqtt_topic}/bearing_{ball_bearing}"

                data_dict = data2dict(headers, row, units=units)
                payload = as_json(data_dict)

                print(f"[telemetry] sending to `{topic_device}': bearing={ball_bearing}, humidity={row[2]}%, vibration={row[3]}")

                publish.single(
                    topic=topic_device,
                    payload=payload,
                    qos=mqtt_qos,
                    hostname=broker_addr,
                    port=port,
                    auth=mqtt_auth,
                    tls=tls_arg.copy() if tls_arg else None,
                )

            except Exception as e:
                print(f"[telemetry] processing error: {e}")

            sleep_time = max(0, random.gauss(sleep_t, sleep_t_sd))
            die_event.wait(timeout=sleep_time)
        else:
            event.wait(timeout=1)

    print("[telemetry] killing thread")

def main(conf):
    event = threading.Event()
    die_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda a, b: signal_handler(a, b, die_event))

    telemetry_thread = threading.Thread(
        target=telemetry,
        name="telemetry",
        args=(
            conf["SLEEP_TIME"],
            conf["SLEEP_TIME_SD"],
            event,
            die_event,
            conf["MQTT_TOPIC_PUB"],
            conf["MQTT_BROKER_ADDR"],
            conf["mqtt_auth"],
            conf["MQTT_QOS"],
            conf["TLS"],
            conf["ca_cert_file"],
            conf["tls_insecure"],
        ),
    )

    broker_ping_thread = threading.Thread(
        target=broker_ping,
        name="broker_ping",
        args=(conf["PING_SLEEP_TIME"], conf["PING_SLEEP_TIME_SD"], die_event, conf["MQTT_BROKER_ADDR"], conf["ping_bin"]),
    )

    die_event.clear()
    broker_ping_thread.start()
    telemetry_thread.start()

    while not ping(conf["ping_bin"], conf["MQTT_BROKER_ADDR"]):
        print(f"[  setup  ] Waiting for Broker {conf['MQTT_BROKER_ADDR']}...")
        time.sleep(2)

    while not die_event.is_set():
        event.set()
        die_event.wait(timeout=5)


if __name__ == "__main__":
    for key in config.keys():
        if key in os.environ:
            config[key] = os.environ[key]

    config["MQTT_QOS"] = int(config["MQTT_QOS"])
    for c in ["SLEEP_TIME", "SLEEP_TIME_SD", "PING_SLEEP_TIME"]:
        config[c] = float(config[c])

    config["ping_bin"] = shutil.which("ping")
    if not config["ping_bin"]:
        sys.exit("No ping binary found")

    if config["MQTT_AUTH"]:
        user_pass = config["MQTT_AUTH"].split(":", 1)
        if len(user_pass) == 1:
            config["mqtt_auth"] = {"username": user_pass[0], "password": None}
        else:
            config["mqtt_auth"] = {"username": user_pass[0], "password": user_pass[-1]}
    else:
        config["mqtt_auth"] = None

    if config["TLS"]:
        config["TLS"] = True
        config["ca_cert_file"] = "/iot-sim-ca.crt"
        config["tls_insecure"] = str(config["TLS_INSECURE"]).casefold() == "true"
    else:
        config["TLS"] = False
        config["ca_cert_file"] = None
        config["tls_insecure"] = None

    main(config)
