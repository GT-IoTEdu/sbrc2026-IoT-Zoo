#!/usr/bin/env bash
set -euo pipefail
TARGET_NET="${1:-${TARGET_NET:-}}"
: "${TARGET_NET:?target network/CIDR required}"
TIMEOUT_MS="${TIMEOUT_MS:-100}"
RETRIES="${RETRIES:-1}"
echo "[attack] ping_sweep target_net=${TARGET_NET} timeout_ms=${TIMEOUT_MS} retries=${RETRIES}"
fping -a -g -t "${TIMEOUT_MS}" -r "${RETRIES}" "${TARGET_NET}" 2>/dev/null || true
echo "[attack] ping_sweep completed"
