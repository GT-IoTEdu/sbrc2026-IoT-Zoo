#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

exec "$SCRIPT_DIR/run_full.sh" --topology "$PROJECT_ROOT/topology_l3_segmented_institutional.yaml" "$@"
