#!/usr/bin/env bash
set -euo pipefail
python3 run_experiment.py --topology topology_l3_segmented_institutional.yaml "$@"
