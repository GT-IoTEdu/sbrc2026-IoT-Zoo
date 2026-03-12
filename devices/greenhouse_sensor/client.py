import lzma
import os
import random
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
import json
import paho.mqtt.publish as publish
import csv

config = {"MQTT_BROKER_ADDR": "localhost",
          "MQTT_TOPIC_PUB": "greenhouse/env",
          "MQTT_AUTH": "",
          "MQTT_QOS": 0,
          "TLS": "",
          "TLS_INSECURE": "false",
          "SLEEP_TIME": 600,
          "SLEEP_TIME_SD": 10,
          "PING_SLEEP_TIME": 60,
          "PING_SLEEP_TIME_SD": 1,
          "ACTIVE_TIME": 60,
          "ACTIVE_TIME_SD": 0,
          "INACTIVE_TIME": 0,
          "INACTIVE_TIME_SD": 0,
          "NTP_SERVER": "localhost",
          "NTP_SLEEP_TIME": 60,
          "NTP_SLEEP_TIME_SD": 0}


def readloop(file, openfunc=open, skipfirst=True):
    """Read a file line by line. If EOF, start from beginning."""
    with openfunc(file, "r") as f:
        while True:
            if skipfirst:
                f.readline()
            for line in f:
                if isinstance(line, bytes):
                    yield line.decode(encoding="utf-8")
                else:
                    yield line
            f.seek(0, 0)


def data2dict(colnames, data, units=None, extra=None):
    """Convert dataset csv line to dictionary"""
    if not units:
        units = [None for _ in range(len(colnames))]

    values = [{"value": v, "unit": u} if u else v for v,u in zip(data, units)]
    out = dict(zip(colnames, values))

    if extra:
        for k, v in extra:
            out[k] = v

    return out
def as_json(payload):
    return json.dumps(payload)

def build_xml_simple(d):
    """Crappy dictionary to xml converter. Low level."""
    out = ""
    for key, val in d.items():
        out += f"<{key}>"
        if isinstance(val, dict):
            out += build_xml_simple(val)
        else:
            out += str(val)
        out += f"</{key}>"
    return out


def as_xml(payload, rootname="root"):
    """Convert dictionary to a simple XML."""
    out = '<?xml version="1.0" encoding="UTF-8"?>'
    out += build_xml_simple({rootname: payload})
    return out


def signal_handler(signum, stackframe, event):
    """Set the event flag to signal all threads to terminate."""
    print(f"Handling signal {signum}")
    event.set()


def ping(bin_path, destination, attempts=3, wait=10):
    """Check if destination responds to ICMP echo requests."""
    for i in range(attempts):
        result = subprocess.run([bin_path, "-c1", destination], capture_output=False, check=False)
        if result.returncode == 0 or i==attempts-1:
            return result.returncode == 0
        time.sleep(wait)
    return result.returncode == 0


def broker_ping(sleep_t, sleep_t_sd, die_event, broker_addr, ping_bin):
    """Periodically send ICMP echo requests to the MQTT broker."""
    while not die_event.is_set():
        print(f"[  ping   ] pinging {broker_addr}...", end="")

        if ping(ping_bin, broker_addr, attempts=1, wait=1):
            print("...OK.")
        else:
            print("...ERROR!")

        sleep_time = random.gauss(sleep_t, sleep_t_sd)
        sleep_time = sleep_t if sleep_time < 0 else sleep_time
        print(f"[  ping   ] sleeping for {sleep_time}s")
        die_event.wait(timeout=sleep_time)
    print("[  ping   ] killing thread")


def ntp_client(sleep_t, sleep_t_sd, die_event, ntp_server, ntp_bin):
    """Periodically poll NTP server."""
    cmd = [ntp_bin, '--ipv4', ntp_server]
    while not die_event.is_set():
        print(f"[   ntp   ] polling NTP server {ntp_server}")

        result = subprocess.run(cmd, capture_output=False, check=False)
        if result.returncode > 0:
            print(f"[   ntp   ] {cmd[0]} failed with return code {result.returncode}")

        sleep_time = random.gauss(sleep_t, sleep_t_sd)
        sleep_time = sleep_t if sleep_time < 0 else sleep_time
        print(f"[   ntp   ] sleeping for {sleep_time}s")
        die_event.wait(timeout=sleep_time)
    print("[   ntp   ] killing thread")


def telemetry(sleep_t, sleep_t_sd, event, die_event, mqtt_topic, broker_addr, mqtt_auth, mqtt_qos, mqtt_tls, mqtt_cacert, mqtt_tls_insecure):
    """Periodically send sensor data to the MQTT broker."""
    print("[telemetry] starting thread")
    dataset_fname = "/dataset.csv.xz"
    dataset_sep = ","
   
    headers = ["Date",
                       "temperature",
                       "humidity",
                       "water_level",
                       "N",
                       "P",
                       "K",
                       "Fan_actuator_OFF",
                       "Fan_actuator_ON",
                       "Watering_plant_pump_OFF ",
                       "Watering_plant_pump_ON",
                       "Water_pump_actuator_OFF",
                       "Water_pump_actuator_ON",]
    units = ["YYYY/MM/DD",
                     "°C",
                     "%",
                     "%",
                     "The nitrogen level in the soil, scaled from 0 to 255",
                     "The phosphorus level in the soil, scaled from 0 to 255",
                     "The potassium level in the soil, scaled from 0 to 255.", None,None,None,None,None,None,]

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

                # created_at (string timestamp)
                row[0] = row[0].strip()
                # entry_id (int)
                row[1] = int(row[1])
                # Temperature (C)
                row[2] = int(row[2])
                # Turbidity (NTU)
                row[3] = int(row[3])
                # Dissolved Oxygen (g/ml)
                row[4] = int(row[4])
                # PH
                row[5] = int(row[5])
                # Ammonia (g/ml)
                row[6] = int(row[6])
                # Nitrate (g/ml)
                row[7] = float(row[7])
                # Population
                row[8] = float(row[8])
                # Fish_Length (cm)
                row[9] = float(row[9])
                # Fish_Weight (g)
                row[10] = float(row[10])
                row[11] = float(row[11])
                # Fish_Weight (g)
                row[12] = float(row[12])

                data_dict = data2dict(headers, row, units=units)
                payload = as_json(data_dict)

                print(
                    f"[telemetry] sending to `{mqtt_topic}': "
                    f"temp={row[2]} C, P={row[5]}, Humidity={row[3]} NTU, "
                    f"N={row[4]} g/ml, K={row[8]}"
                )

                publish.single(
                    topic=mqtt_topic,
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
    """Manages the other threads."""
    event = threading.Event()
    die_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda a,b:signal_handler(a, b, die_event))

    telemetry_thread = threading.Thread(target=telemetry,
                                        name="telemetry",
                                        args=(conf["SLEEP_TIME"],
                                              conf["SLEEP_TIME_SD"],
                                              event, die_event,
                                              conf["MQTT_TOPIC_PUB"], conf["MQTT_BROKER_ADDR"], conf["mqtt_auth"], conf["MQTT_QOS"],
                                              conf["TLS"], conf["ca_cert_file"], conf["tls_insecure"]),
                                        kwargs={})
    broker_ping_thread = threading.Thread(target=broker_ping,
                                            name="broker_ping",
                                            args=(conf["PING_SLEEP_TIME"], conf["PING_SLEEP_TIME_SD"], die_event, conf["MQTT_BROKER_ADDR"], conf["ping_bin"]),
                                            kwargs={},
                                            daemon=False)
    ntp_client_thread = threading.Thread(target=ntp_client,
                                         name="ntp_client",
                                         args=(conf["NTP_SLEEP_TIME"], conf["NTP_SLEEP_TIME_SD"], die_event, conf["NTP_SERVER"], conf["ntp_bin"]),
                                         kwargs={},
                                         daemon=False)

    die_event.clear()
    broker_ping_thread.start()
    telemetry_thread.start()
    if conf["ntp_bin"]:
        ntp_client_thread.start()
    die_event.wait(timeout=5)

    print("[  main   ] starting loop")

    while not die_event.is_set():
        event.set()
        print("[  main   ] telemetry ON")
        die_event.wait(timeout=max(0, random.gauss(conf["ACTIVE_TIME"], conf["ACTIVE_TIME_SD"])))
        if conf["INACTIVE_TIME"] > 0:
            event.clear()
            print("[  main   ] telemetry OFF")
            die_event.wait(timeout=max(0, random.gauss(conf["INACTIVE_TIME"], conf["INACTIVE_TIME_SD"])))

    print("[  main   ] exit")


if __name__ == "__main__":
    for key in config.keys():
        try:
            config[key] = os.environ[key]
        except KeyError:
            pass

    config["MQTT_QOS"] = int(config["MQTT_QOS"])
    for c in ("SLEEP_TIME", "SLEEP_TIME_SD", "PING_SLEEP_TIME", "PING_SLEEP_TIME_SD", "ACTIVE_TIME", "ACTIVE_TIME_SD", "INACTIVE_TIME", "INACTIVE_TIME_SD", "NTP_SLEEP_TIME", "NTP_SLEEP_TIME_SD"):
        config[c] = float(config[c])

    config["MQTT_TOPIC_PUB"] = f"{config['MQTT_TOPIC_PUB']}/sensor-{socket.gethostname()}"
    print(f"[  setup  ] selected MQTT topic: {config['MQTT_TOPIC_PUB']}")

    if config["MQTT_AUTH"]:
        user_pass = config["MQTT_AUTH"].split(":", 1)
        if len(user_pass) == 1:
            config["mqtt_auth"] = {"username": user_pass[0], "password": None}
        else:
            config["mqtt_auth"] = {"username": user_pass[0], "password": user_pass[-1]}
    else:
        config["mqtt_auth"] = None
    print(f"[  setup  ] MQTT authentication: {config['mqtt_auth']}")

    config["ping_bin"] = shutil.which("ping")
    if not config["ping_bin"]:
        sys.exit("[  setup  ] No 'ping' binary found. Exiting.")

    config["ntp_bin"] = shutil.which("sntp")
    if not config["ntp_bin"]:
        print("[  setup  ] No 'sntp' binary found.")
    if config["NTP_SLEEP_TIME"] <= 0:
        config["ntp_bin"] = None
        print("[  setup  ] Disabling ntp.")

    # Loop infinito até o Broker responder
    while not ping(config["ping_bin"], config["MQTT_BROKER_ADDR"]):
        print(f"[setup] {config['MQTT_BROKER_ADDR']} is down. Retrying in 2s...")
        time.sleep(2)
    print(f"[setup] Broker {config['MQTT_BROKER_ADDR']} is UP!")

    if config["TLS"]:
        config["TLS"] = True
        config["ca_cert_file"] = "/iot-sim-ca.crt"
        # With tls_insecure=True communications are encrypted but the server hostname verification is disabled
        config["tls_insecure"] = config["TLS_INSECURE"].casefold() == "true"
        if not os.path.isfile(config["ca_cert_file"]):
            sys.exit(f"[  setup  ] TLS enabled but ca cert file `{config['ca_cert_file']}' does not exist. Exiting.")
    else:
        config["TLS"] = False
        config["ca_cert_file"] = None
        config["tls_insecure"] = None

    print(f"[  setup  ] TLS enabled: {config['TLS']}, ca cert: {config['ca_cert_file']}, TLS insecure: {config['tls_insecure']}")

    main(config)