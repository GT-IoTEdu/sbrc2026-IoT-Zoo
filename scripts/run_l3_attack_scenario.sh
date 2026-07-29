#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <attack_scenario.yaml> [run_experiment.py options]" >&2
  echo "Example: $0 attack_scenarios/mqtt_publisher_flood.yaml --time 180 --output /tmp/iot_zoo_l3.pcap" >&2
  exit 2
fi

SCENARIO="$1"
shift
python3 run_experiment.py \
  --topology topology_l3_segmented_institutional.yaml \
  --attack-scenario "$SCENARIO" \
  "$@"
