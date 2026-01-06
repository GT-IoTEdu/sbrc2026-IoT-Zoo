#!/usr/bin/env python3

import json
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
import lzma
from pathlib import Path

import paho.mqtt.client as mqtt


config = {
    "MQTT_BROKER_ADDR": "localhost",
    "MQTT_TOPIC_PUB": "mhealth",
    "MQTT_AUTH": "",
    "MQTT_QOS": 0,
    "TLS": "",
    "TLS_INSECURE": "false",
    "SLEEP_TIME": 0.02,          # não usamos diretamente aqui, mas mantemos para padrão
    "SLEEP_TIME_SD": 0.0,
    "PING_SLEEP_TIME": 60,
    "PING_SLEEP_TIME_SD": 1,
    "ACTIVE_TIME": 3600,         # tempo "online" padrão (evento ligado)
    "ACTIVE_TIME_SD": 0,
    "INACTIVE_TIME": 0,          # 0 = nunca desligar via ACTIVE/INACTIVE, só pelo EOF
    "INACTIVE_TIME_SD": 0,
    "NTP_SERVER": "localhost",
    "NTP_SLEEP_TIME": 60,
    "NTP_SLEEP_TIME_SD": 0,
    # parâmetros específicos do MHEALTH
    "SUBJECT_ID": 1,
    "SAMPLE_RATE_HZ": 50.0,
    "SPEED_FACTOR": 1.0,        # >1 acelera o tempo (50Hz/speed_factor na prática)
    "OFFLINE_TIME": 300.0,       # segundos "desligado" após chegar ao fim do arquivo
    "OFFLINE_TIME_SD": 0.0,
}


COLUMN_NAMES = [
    "acc_chest_x", "acc_chest_y", "acc_chest_z",
    "ecg_lead1", "ecg_lead2",
    "acc_ankle_x", "acc_ankle_y", "acc_ankle_z",
    "gyro_ankle_x", "gyro_ankle_y", "gyro_ankle_z",
    "mag_ankle_x", "mag_ankle_y", "mag_ankle_z",
    "acc_arm_x", "acc_arm_y", "acc_arm_z",
    "gyro_arm_x", "gyro_arm_y", "gyro_arm_z",
    "mag_arm_x", "mag_arm_y", "mag_arm_z",
    "label",
]


def signal_handler(signum, stackframe, event):
    """Set the event flag to signal all threads to terminate."""
    print(f"Handling signal {signum}")
    event.set()


def ping(bin_path, destination, attempts=3, wait=10):
    """Check if destination responds to ICMP echo requests."""
    for i in range(attempts):
        result = subprocess.run([bin_path, "-c1", destination], capture_output=False, check=False)
        if result.returncode == 0 or i == attempts - 1:
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
    cmd = [ntp_bin, "--ipv4", ntp_server]
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


def setup_mqtt_client(broker_addr, mqtt_auth, mqtt_tls, mqtt_cacert, mqtt_tls_insecure):
    """Cria um cliente MQTT persistente (mantém conexão aberta)."""
    client = mqtt.Client()

    if mqtt_auth is not None:
        client.username_pw_set(mqtt_auth.get("username"), mqtt_auth.get("password"))

    if mqtt_tls:
        client.tls_set(ca_certs=mqtt_cacert)
        client.tls_insecure_set(mqtt_tls_insecure)
        port = 8883
    else:
        port = 1883

    client.connect(broker_addr, port, keepalive=60)
    client.loop_start()
    print(f"[telemetry] MQTT conectado em {broker_addr}:{port}")
    return client


def telemetry(
    sample_rate_hz,
    speed_factor,
    offline_t,
    offline_t_sd,
    event,
    die_event,
    mqtt_topic,
    broker_addr,
    mqtt_auth,
    mqtt_qos,
    mqtt_tls,
    mqtt_cacert,
    mqtt_tls_insecure,
    subject_id,
):
    """Envia dados do MHEALTH como se fossem de um wearable IoT."""
    print("[telemetry] starting thread")

    dataset_dir = Path("/mhealth")
    dataset_fname = dataset_dir / f"mHealth_subject{subject_id}.log.xz"

    if not dataset_fname.exists():
        print(f"[telemetry] arquivo `{dataset_fname}` não encontrado. Encerrando.")
        die_event.set()
        print("[telemetry] killing thread")
        return

    base_dt = 1.0 / float(sample_rate_hz)
    dt = base_dt / float(speed_factor)

    # cliente MQTT persistente
    client = setup_mqtt_client(broker_addr, mqtt_auth, mqtt_tls, mqtt_cacert, mqtt_tls_insecure)

    # Tópico base deste dispositivo (segue o padrão 'topic/id-hostname/...'):
    # mqtt_topic já vem com /id-<hostname> montado no main
    device_topic = f"{mqtt_topic}/subject-{subject_id}"

    cycle = 0

    try:
        while not die_event.is_set():
            # espera o "ON" do dispositivo (controlado pelo main via ACTIVE/INACTIVE)
            if not event.is_set():
                print("[telemetry] zZzzZZz sleeping... zzZzZZz")
                die_event.wait(timeout=1)
                continue

            cycle += 1
            print(f"[telemetry] >>> subject{subject_id} ONLINE (ciclo {cycle})")
            seq = 0

            with lzma.open(dataset_fname, "rt", encoding="utf-8") as f:
                finished_normally = True
                for line in f:
                    if die_event.is_set():
                        finished_normally = False
                        break
                    if not event.is_set():
                        # desligado pelo ACTIVE/INACTIVE do main
                        finished_normally = False
                        print("[telemetry] evento desligado pelo main, pausando leitura.")
                        break

                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split()
                    if len(parts) != len(COLUMN_NAMES):
                        print(
                            f"[telemetry] WARN: linha com {len(parts)} colunas "
                            f"(esperado {len(COLUMN_NAMES)}). Pulando."
                        )
                        continue

                    try:
                        values = [float(x) for x in parts]
                    except ValueError:
                        print("[telemetry] WARN: falha ao converter linha para float. Pulando.")
                        continue

                    record = dict(zip(COLUMN_NAMES, values))
                    record["t"] = seq * base_dt  # tempo sintético da sessão
                    record["subject_id"] = subject_id
                    record["seq"] = seq

                    payload = json.dumps(record)
                    # Publica em um único tópico por dispositivo
                    # Ex: mhealth/id-hostname/subject-1
                    try:
                        client.publish(device_topic, payload, qos=mqtt_qos)
                    except Exception as e:
                        print(f"[telemetry] erro ao publicar MQTT: {e}")
                        die_event.set()
                        finished_normally = False
                        break

                    seq += 1
                    time.sleep(dt)

            if die_event.is_set():
                break

            if finished_normally:
                # chegou ao fim do arquivo → dispositivo "desliga" por um tempo
                offline_time = random.gauss(offline_t, offline_t_sd)
                offline_time = offline_t if offline_time < 0 else offline_time
                print(
                    f"[telemetry] <<< subject{subject_id} OFFLINE (fim do arquivo). "
                    f"Ficará desligado por {offline_time}s."
                )
                die_event.wait(timeout=offline_time)
            else:
                # pausa causada por main (ACTIVE/INACTIVE) ou erro
                pass

        print("[telemetry] killing thread")
    finally:
        try:
            client.loop_stop()
            client.disconnect()
            print("[telemetry] MQTT desconectado.")
        except Exception:
            pass


def main(conf):
    """Manages the other threads."""
    event = threading.Event()
    die_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda a, b: signal_handler(a, b, die_event))

    telemetry_thread = threading.Thread(
        target=telemetry,
        name="telemetry",
        args=(
            conf["SAMPLE_RATE_HZ"],
            conf["SPEED_FACTOR"],
            conf["OFFLINE_TIME"],
            conf["OFFLINE_TIME_SD"],
            event,
            die_event,
            conf["MQTT_TOPIC_PUB"],
            conf["MQTT_BROKER_ADDR"],
            conf["mqtt_auth"],
            conf["MQTT_QOS"],
            conf["TLS"],
            conf["ca_cert_file"],
            conf["tls_insecure"],
            conf["SUBJECT_ID"],
        ),
        kwargs={},
    )

    broker_ping_thread = threading.Thread(
        target=broker_ping,
        name="broker_ping",
        args=(
            conf["PING_SLEEP_TIME"],
            conf["PING_SLEEP_TIME_SD"],
            die_event,
            conf["MQTT_BROKER_ADDR"],
            conf["ping_bin"],
        ),
        kwargs={},
        daemon=False,
    )

    ntp_client_thread = threading.Thread(
        target=ntp_client,
        name="ntp_client",
        args=(
            conf["NTP_SLEEP_TIME"],
            conf["NTP_SLEEP_TIME_SD"],
            die_event,
            conf["NTP_SERVER"],
            conf["ntp_bin"],
        ),
        kwargs={},
        daemon=False,
    )

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
            die_event.wait(
                timeout=max(0, random.gauss(conf["INACTIVE_TIME"], conf["INACTIVE_TIME_SD"]))
            )

    print("[  main   ] exit")


if __name__ == "__main__":
    # sobrescreve config com variáveis de ambiente (mesmo padrão do building)
    for key in config.keys():
        try:
            config[key] = os.environ[key]
        except KeyError:
            pass

    config["MQTT_QOS"] = int(config["MQTT_QOS"])

    for c in (
        "SLEEP_TIME",
        "SLEEP_TIME_SD",
        "PING_SLEEP_TIME",
        "PING_SLEEP_TIME_SD",
        "ACTIVE_TIME",
        "ACTIVE_TIME_SD",
        "INACTIVE_TIME",
        "INACTIVE_TIME_SD",
        "NTP_SLEEP_TIME",
        "NTP_SLEEP_TIME_SD",
        "SAMPLE_RATE_HZ",
        "SPEED_FACTOR",
        "OFFLINE_TIME",
        "OFFLINE_TIME_SD",
    ):
        config[c] = float(config[c])

    config["SUBJECT_ID"] = int(config["SUBJECT_ID"])

    # adiciona id do host ao tópico, como no building
    config["MQTT_TOPIC_PUB"] = f"{config['MQTT_TOPIC_PUB']}/id-{socket.gethostname()}"
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

    print(f"[  setup  ] Aguardando Broker {config['MQTT_BROKER_ADDR']}...")
    
    # Loop infinito até conseguir pingar o Broker
    while not ping(config["ping_bin"], config["MQTT_BROKER_ADDR"]):
        print(f"[  setup  ] Broker indisponível. Retentando em 5s...")
        time.sleep(5)
    
    print(f"[  setup  ] Broker ONLINE! Iniciando serviços...")

    if config["TLS"]:
        config["TLS"] = True
        config["ca_cert_file"] = "/iot-sim-ca.crt"
        config["tls_insecure"] = config["TLS_INSECURE"].casefold() == "true"
        if not os.path.isfile(config["ca_cert_file"]):
            sys.exit(
                f"[  setup  ] TLS enabled but ca cert file `{config['ca_cert_file']}' does not exist. Exiting."
            )
    else:
        config["TLS"] = False
        config["ca_cert_file"] = None
        config["tls_insecure"] = None

    print(
        f"[  setup  ] TLS enabled: {config['TLS']}, "
        f"ca cert: {config['ca_cert_file']}, TLS insecure: {config['tls_insecure']}"
    )

    main(config)
