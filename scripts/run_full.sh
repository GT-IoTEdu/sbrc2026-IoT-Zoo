#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINERNET_PATH="${CONTAINERNET_PATH:-${HOME}/containernet}"

# Dry-run/help do not require root. Real Containernet execution does.
NEEDS_ROOT=1
for arg in "$@"; do
  case "$arg" in
    --dry-run|-h|--help)
      NEEDS_ROOT=0
      ;;
  esac
done

if [[ "$NEEDS_ROOT" -eq 1 && "${EUID}" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

# When executed through sudo, HOME may be /root. Recover the original user's containernet path when possible.
if [[ -n "${SUDO_USER:-}" && "$CONTAINERNET_PATH" == "/root/containernet" ]]; then
  CONTAINERNET_PATH="/home/${SUDO_USER}/containernet"
fi

# Track output for ownership restoration after sudo execution.
OUTPUT="/tmp/iot_zoo_full.pcap"
ARGS=("$@")
i=0
while [[ $i -lt ${#ARGS[@]} ]]; do
  case "${ARGS[$i]}" in
    -o|--output)
      if [[ $((i + 1)) -lt ${#ARGS[@]} ]]; then
        OUTPUT="${ARGS[$((i + 1))]}"
      fi
      i=$((i + 2)) ;;
    --output=*)
      OUTPUT="${ARGS[$i]#--output=}"; i=$((i + 1)) ;;
    *)
      i=$((i + 1)) ;;
  esac
done

cd "$PROJECT_ROOT"
PYTHONPATH="$CONTAINERNET_PATH" python3 run_experiment.py "$@"

if [[ -n "${SUDO_USER:-}" ]]; then
  # Single capture uses OUTPUT directly. Multi-point capture appends _<capture-point> before the extension.
  if [[ -f "$OUTPUT" ]]; then
    chown "${SUDO_USER}:${SUDO_USER}" "$OUTPUT" || true
  fi
  stem="${OUTPUT%.*}"
  ext="${OUTPUT##*.}"
  if [[ "$stem" != "$OUTPUT" ]]; then
    for f in "${stem}"_*."${ext}"; do
      [[ -e "$f" ]] && chown "${SUDO_USER}:${SUDO_USER}" "$f" || true
    done
  fi
fi
