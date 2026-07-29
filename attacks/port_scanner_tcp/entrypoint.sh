#!/usr/bin/env bash
set -euo pipefail
TARGETS="${TARGETS:-${1:-}}"
: "${TARGETS:?target IP/FQDN/CIDR required}"
PORTS="${PORTS:-1883,8554,80,443}"
TIMING="${TIMING:-T3}"
MAX_RETRIES="${MAX_RETRIES:-1}"
HOST_TIMEOUT="${HOST_TIMEOUT:-20s}"
echo "[attack] port_scanner_tcp targets=${TARGETS} ports=${PORTS} timing=${TIMING}"
for target in ${TARGETS}; do
  nmap -sT -Pn -${TIMING} --max-retries "${MAX_RETRIES}" --host-timeout "${HOST_TIMEOUT}" -p "${PORTS}" "${target}" || true
done
echo "[attack] port_scanner_tcp completed"
