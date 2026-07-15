#!/usr/bin/env bash
set -euo pipefail

PCAP_DIR="/tmp"
PREFIX="iot_zoo_l3"
OUT_DIR="./merged_l3"
MODE="domain"   # domain, router, all

usage() {
  cat <<EOF
Usage: $0 [--pcap-dir DIR] [--prefix PREFIX] [--out-dir DIR] [--mode domain|router|all]

Modes:
  domain  Merge only domain/access switch captures: infra + six domain switches.
  router  Merge only router interface captures.
  all     Merge every L3 capture point. Use with care because this can duplicate packets.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pcap-dir) PCAP_DIR="$2"; shift 2 ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if ! command -v mergecap >/dev/null 2>&1; then
  echo "mergecap not found. Install with: sudo apt-get install -y tshark" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

DOMAIN_CAPS=(
  sw_infra
  sw_hospital
  sw_university
  sw_industrial
  sw_school
  sw_cctv
  sw_outdoor
)
ROUTER_CAPS=(
  r_edge_external
  r_edge_infra
  r_field_infra
  r_field_hospital
  r_field_university
  r_field_industrial
  r_field_school
  r_field_cctv
  r_field_outdoor
)

case "$MODE" in
  domain) CAPS=("${DOMAIN_CAPS[@]}"); OUT="$OUT_DIR/${PREFIX}_domain_switches_merged.pcapng" ;;
  router) CAPS=("${ROUTER_CAPS[@]}"); OUT="$OUT_DIR/${PREFIX}_router_interfaces_merged.pcapng" ;;
  all) CAPS=("${DOMAIN_CAPS[@]}" "${ROUTER_CAPS[@]}"); OUT="$OUT_DIR/${PREFIX}_all_capture_points_merged.pcapng" ;;
  *) echo "Invalid mode: $MODE" >&2; usage; exit 1 ;;
esac

FILES=()
for cap in "${CAPS[@]}"; do
  f="$PCAP_DIR/${PREFIX}_${cap}.pcap"
  if [[ -s "$f" ]]; then
    FILES+=("$f")
  else
    echo "WARNING: missing or empty: $f" >&2
  fi
done

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "No input PCAPs found." >&2
  exit 2
fi

mergecap -w "$OUT" "${FILES[@]}"
echo "Merged ${#FILES[@]} PCAPs -> $OUT"

echo "Important: merged multi-point captures may contain duplicate observations of the same packet."
echo "For ML, prefer extracting features per capture point and then concatenating rows with a capture_point/domain column."
