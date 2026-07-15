#!/usr/bin/env bash
set -u

ERRORS=0
WARNINGS=0

ok() { printf "[OK]   %s\n" "$1"; }
warn() { printf "[WARN] %s\n" "$1"; WARNINGS=$((WARNINGS+1)); }
fail() { printf "[FAIL] %s\n" "$1"; ERRORS=$((ERRORS+1)); }
info() { printf "[INFO] %s\n" "$1"; }

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINERNET_PATH="${CONTAINERNET_PATH:-$HOME/containernet}"

printf "IoT-Zoo environment check\n"
printf "Project root: %s\n" "$PROJECT_ROOT"
printf "Containernet path: %s\n\n" "$CONTAINERNET_PATH"

# OS detection
if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  DETECTED="${PRETTY_NAME:-unknown}"
  info "Detected OS: $DETECTED"
  if [[ "${ID:-}" == "ubuntu" && ( "${VERSION_ID:-}" == "20.04" || "${VERSION_ID:-}" == "22.04" ) ]]; then
    ok "Supported Ubuntu LTS detected: ${VERSION_ID}"
  elif grep -qi microsoft /proc/version 2>/dev/null; then
    fail "WSL/WSL2 detected. Use an Ubuntu Server VM instead."
  else
    warn "This OS is not officially validated. Recommended: Ubuntu Server 20.04 or 22.04 LTS."
  fi
else
  warn "Could not detect OS from /etc/os-release."
fi

# Commands
for cmd in git python3 pip3 docker tcpdump xz unxz ethtool ip iptables; do
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "Command available: $cmd"
  else
    fail "Missing command: $cmd"
  fi
done

for cmd in ovs-vsctl ovs-ofctl; do
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "Open vSwitch command available: $cmd"
  else
    fail "Missing Open vSwitch command: $cmd"
  fi
done

if command -v tshark >/dev/null 2>&1; then
  ok "Optional command available: tshark"
else
  warn "Optional command missing: tshark. PCAP conversion/inspection may be limited."
fi

# Services
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet docker 2>/dev/null; then
    ok "Docker service is active"
  else
    fail "Docker service is not active"
  fi
  if systemctl is-active --quiet openvswitch-switch 2>/dev/null; then
    ok "Open vSwitch service is active"
  else
    warn "openvswitch-switch service is not active or not managed by systemctl"
  fi
fi

# Docker daemon
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    ok "Docker daemon is reachable without sudo"
  elif sudo -n docker info >/dev/null 2>&1; then
    ok "Docker daemon is reachable with sudo"
  else
    fail "Docker daemon is not reachable. Check service status and user permissions."
  fi
fi

# Python imports
if python3 -c "import sys; print(sys.version)" >/dev/null 2>&1; then
  ok "Python 3 is working"
else
  fail "Python 3 is not working"
fi

if python3 -c "import yaml, pandas, paho.mqtt.client" >/dev/null 2>&1; then
  ok "Python packages available: PyYAML, pandas, paho-mqtt"
else
  warn "Python packages PyYAML, pandas and/or paho-mqtt are missing in the current interpreter"
fi

if python3 -c "import scapy" >/dev/null 2>&1; then
  ok "Optional Python package available: scapy"
else
  warn "Optional Python package missing: scapy. PCAP conversion utilities may be limited."
fi

# Containernet import under sudo/root context
if sudo -n env PYTHONPATH="$CONTAINERNET_PATH" python3 -c "from mininet.net import Containernet" >/dev/null 2>&1; then
  ok "Containernet import works through the run-script PYTHONPATH strategy"
elif sudo -n python3 -c "from mininet.net import Containernet" >/dev/null 2>&1; then
  ok "Containernet import works with system Python"
else
  fail "Containernet import failed. Install Containernet or set CONTAINERNET_PATH."
fi

# Project files
for path in run_experiment.py topology_loader.py catalog.yaml topology.yaml topology_example_tree.yaml demo_experiment.py devices scripts scripts/prepare_demo_data.sh sample_data/urban_observatory; do
  if [[ -e "$PROJECT_ROOT/$path" ]]; then
    ok "Project path found: $path"
  else
    fail "Missing project path: $path"
  fi
done

# Config dry-run validation (does not require Containernet)
if python3 "$PROJECT_ROOT/run_experiment.py" --topology "$PROJECT_ROOT/topology.yaml" --dry-run >/tmp/iot_zoo_config_check.log 2>&1; then
  ok "Default configurable topology validates in dry-run mode"
else
  fail "Default topology dry-run failed. See /tmp/iot_zoo_config_check.log"
fi

if python3 "$PROJECT_ROOT/run_experiment.py" --topology "$PROJECT_ROOT/topology_example_tree.yaml" --dry-run >/tmp/iot_zoo_tree_check.log 2>&1; then
  ok "Example tree topology validates in dry-run mode"
else
  warn "Example tree topology dry-run failed. See /tmp/iot_zoo_tree_check.log"
fi

# Dataset checks
URBAN_DATASET_COUNT=$(find "$PROJECT_ROOT/devices/urban_observatory" -type f \( -name "*.csv.xz" -o -name "*.csv" \) 2>/dev/null | wc -l | tr -d ' ')
if [[ "$URBAN_DATASET_COUNT" -gt 0 ]]; then
  ok "Urban Observatory source datasets found: $URBAN_DATASET_COUNT file(s)"
else
  warn "No Urban Observatory .csv/.csv.xz source files found. Demo/full data preparation will require datasets."
fi

INVALID_XZ_COUNT=0
while IFS= read -r -d '' file; do
  if ! xz -t "$file" >/dev/null 2>&1; then
    INVALID_XZ_COUNT=$((INVALID_XZ_COUNT+1))
    warn "Invalid .xz file: $file"
  fi
done < <(find "$PROJECT_ROOT/devices" -type f -name "*.xz" -print0 2>/dev/null)
if [[ "$INVALID_XZ_COUNT" -eq 0 ]]; then
  ok "Compressed .xz artifacts are valid"
fi

DEMO_CSV_COUNT=$(find "$PROJECT_ROOT/sample_data/urban_observatory" -type f -name "*.csv" 2>/dev/null | wc -l | tr -d ' ')
if [[ "$DEMO_CSV_COUNT" -gt 0 ]]; then
  ok "Generated basic demo CSV files found: $DEMO_CSV_COUNT file(s)"
else
  warn "Basic demo data not prepared. Run ./scripts/prepare_demo_data.sh --duration 120 --clean"
fi

DATASET_ARTIFACT_COUNT=$(find "$PROJECT_ROOT/devices" -type f \( -name "*.csv.xz" -o -name "*.txt.xz" -o -name "*.mp4" \) 2>/dev/null | wc -l | tr -d ' ')
if [[ "$DATASET_ARTIFACT_COUNT" -gt 0 ]]; then
  ok "Device dataset/video artifacts found: $DATASET_ARTIFACT_COUNT file(s)"
else
  warn "No dataset/video artifacts found under devices/. Full image build may fail until datasets are available."
fi

# Demo images
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  for image in myzoo/mqtt_broker myzoo/urban_sensor; do
    if docker image inspect "$image" >/dev/null 2>&1; then
      ok "Docker image available: $image"
    else
      warn "Docker image not found: $image. Run ./scripts/build_images.sh --demo"
    fi
  done
fi

printf "\nSummary: %s error(s), %s warning(s).\n" "$ERRORS" "$WARNINGS"
if [[ "$ERRORS" -gt 0 ]]; then
  exit 1
fi
exit 0
