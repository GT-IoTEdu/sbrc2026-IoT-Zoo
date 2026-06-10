#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINERNET_PATH="${CONTAINERNET_PATH:-${HOME}/containernet}"

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

# When executed through sudo, HOME may be /root. Recover the original user's containernet path when possible.
if [[ -n "${SUDO_USER:-}" && "$CONTAINERNET_PATH" == "/root/containernet" ]]; then
  CONTAINERNET_PATH="/home/${SUDO_USER}/containernet"
fi

TIME=120
OUTPUT="/tmp/iot_zoo_demo.pcap"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--time)
      TIME="$2"; shift 2 ;;
    -o|--output)
      OUTPUT="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--time seconds] [--output /tmp/file.pcap]"; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

cd "$PROJECT_ROOT"
PYTHONPATH="$CONTAINERNET_PATH" python3 demo_experiment.py --time "$TIME" --output "$OUTPUT"

echo "Demo finished. Output: $OUTPUT"
if [[ -n "${SUDO_USER:-}" && -f "$OUTPUT" ]]; then
  chown "${SUDO_USER}:${SUDO_USER}" "$OUTPUT" || true
fi
