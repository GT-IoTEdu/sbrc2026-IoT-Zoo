"""Shim de compatibilidade MQTT (paho) -> Zenoh para os clientes do IoT-Zoo.

Os `client.py` dos dispositivos publicam telemetria via `paho-mqtt`, usando ou o
helper `paho.mqtt.publish.single(...)` ou um `paho.mqtt.client.Client` persistente.
Este módulo expõe EXATAMENTE o mesmo subconjunto dessa API, porém redirecionando
as publicações para um router Zenoh (`session.put`). Assim, a variante
`client_zenoh.py` de cada device é uma cópia fiel do `client.py` com APENAS a linha
de import trocada:

    import paho.mqtt.publish as publish   ->  from iotzoo_zenoh import publish
    import paho.mqtt.client  as mqtt       ->  from iotzoo_zenoh import client as mqtt

O endereço (`hostname`) passado às chamadas continua sendo o mesmo injetado por
`MQTT_BROKER_ADDR` — no run com PROTOCOL=zenoh ele aponta para o Zenoh Router. O
`topic` MQTT é usado diretamente como key expression Zenoh (a hierarquia com '/' é
compatível). A porta Zenoh é configurável por `ZENOH_PORT` (default 7447).
"""

import json
import os

import zenoh

_ZENOH_PORT = int(os.environ.get("ZENOH_PORT", "7447"))
_sessions = {}  # host -> zenoh.Session (uma sessão reutilizada por destino)


def _session_for(host):
    sess = _sessions.get(host)
    if sess is None:
        conf = zenoh.Config()
        conf.insert_json5("mode", '"client"')
        conf.insert_json5("connect/endpoints", f'["tcp/{host}:{_ZENOH_PORT}"]')
        sess = zenoh.open(conf)
        _sessions[host] = sess
        print(f"[zenoh] session open -> tcp/{host}:{_ZENOH_PORT}")
    return sess


def _put(host, topic, payload):
    if payload is None:
        payload = b""
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload)
    _session_for(host).put(str(topic), payload)


# --- Emulação de paho.mqtt.publish (helper one-shot) -------------------------
class _PublishModule:
    @staticmethod
    def single(topic, payload=None, qos=0, hostname="localhost", port=1883,
               auth=None, tls=None, **kwargs):
        _put(hostname, topic, payload)


publish = _PublishModule()


# --- Emulação de paho.mqtt.client (cliente persistente) ----------------------
def connack_string(rc):
    return "Connection Accepted." if rc == 0 else f"Connection Refused (rc={rc})."


class _MsgInfo:
    """Mimetiza paho.mqtt.client.MQTTMessageInfo."""
    rc = 0

    def wait_for_publish(self, timeout=None):
        return None

    def is_published(self):
        return True


class Client:
    """Subconjunto de paho.mqtt.client.Client usado pelos devices do IoT-Zoo."""

    def __init__(self, *args, **kwargs):
        self._host = "localhost"
        self.on_connect = None
        self.on_disconnect = None
        self.on_publish = None

    # configurações que não se aplicam ao Zenoh (no-op para manter a API)
    def username_pw_set(self, *args, **kwargs):
        pass

    def tls_set(self, *args, **kwargs):
        pass

    def tls_insecure_set(self, *args, **kwargs):
        pass

    def connect(self, host, port=1883, keepalive=60, *args, **kwargs):
        self._host = host
        _session_for(host)
        if self.on_connect:
            self.on_connect(self, None, {}, 0)
        return 0

    def reconnect(self, *args, **kwargs):
        _session_for(self._host)
        return 0

    def loop_start(self):
        pass

    def loop_stop(self, *args, **kwargs):
        pass

    def loop_forever(self, *args, **kwargs):
        pass

    def publish(self, topic, payload=None, qos=0, retain=False, *args, **kwargs):
        _put(self._host, topic, payload)
        info = _MsgInfo()
        if self.on_publish:
            self.on_publish(self, None, 0)
        return info

    def disconnect(self, *args, **kwargs):
        if self.on_disconnect:
            self.on_disconnect(self, None, 0)
        return 0


class _ClientModule:
    Client = Client
    connack_string = staticmethod(connack_string)
    MQTTv311 = 4
    MQTTv31 = 3


client = _ClientModule()
