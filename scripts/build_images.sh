#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:---help}"

usage() {
  cat <<USAGE
Usage: $0 --demo | --full

Options:
  --demo   Build only the images required by demo_experiment.py.
           Demo data is prepared separately with scripts/prepare_demo_data.sh.
  --full   Build all device images using the datasets stored under devices/.
USAGE
}

build_image() {
  local tag="$1"
  local context="$2"
  echo "--- Building $tag from $context"
  docker build -t "$tag" "$PROJECT_ROOT/$context"
}

case "$MODE" in
  --demo)
    find "$PROJECT_ROOT/devices" -name "*.py" -exec chmod +x {} +
    build_image "iotsim/certificates:latest" "devices/certificates"
    build_image "myzoo/mqtt_broker" "devices/mqtt_broker"
    build_image "myzoo/urban_sensor" "devices/urban_observatory"
    echo "Demo images built successfully. If demo data is not ready, run ./scripts/prepare_demo_data.sh --duration 120 --clean"
    ;;
  --full)
    find "$PROJECT_ROOT/devices" -name "*.py" -exec chmod +x {} +
    build_image "iotsim/certificates:latest" "devices/certificates"
    build_image "myzoo/mqtt_broker" "devices/mqtt_broker"
    build_image "myzoo/urban_sensor" "devices/urban_observatory"
    build_image "myzoo/server_video" "devices/stream_server"
    build_image "myzoo/camera" "devices/ip_camera"
    build_image "myzoo/consumer_video" "devices/stream_consumer"
    build_image "myzoo/cooler_motor" "devices/cooler_motor"
    build_image "myzoo/building_monitor" "devices/building_monitor"
    build_image "myzoo/domotic_monitor" "devices/domotic_monitor"
    build_image "myzoo/air_quality" "devices/air_quality"
    build_image "myzoo/mhealth" "devices/mhealth-device"
    build_image "myzoo/smart_lighting" "devices/smart_lighting"
    build_image "myzoo/environmental_sensors" "devices/environmental_sensors"
    build_image "myzoo/aquaponics_fish_pond" "devices/aquaponics_fish_pond"
    build_image "myzoo/predictive_maintenance" "devices/predictive_maintenance"
    build_image "myzoo/elevator_predictive_maintenance" "devices/elevator_predictive_maintenance"
    build_image "myzoo/traction_elevator" "devices/traction-elevator-predictive-maintenance"
    build_image "myzoo/greenhouse_sensor" "devices/greenhouse_sensor"
    build_image "myzoo/farming_sensor" "devices/farming_sensor"
    build_image "myzoo/nurse_stress" "devices/nurse-stress-prediction"
    build_image "myzoo/smart_building_m5" "devices/smart_building_m5"
    echo "Full image build completed."
    ;;
  --help|-h|help)
    usage
    ;;
  *)
    echo "Unknown option: $MODE" >&2
    usage
    exit 1
    ;;
esac
