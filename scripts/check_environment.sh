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

# -----------------------------------------------------------------------------
# OS detection
# -----------------------------------------------------------------------------

if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  DETECTED="${PRETTY_NAME:-unknown}"
  info "Detected OS: $DETECTED"

  if grep -qi microsoft /proc/version 2>/dev/null; then
    fail "WSL/WSL2 detected. Use an Ubuntu Server VM instead."
  elif [[ "${ID:-}" == "ubuntu" && ( "${VERSION_ID:-}" == "20.04" || "${VERSION_ID:-}" == "22.04" ) ]]; then
    ok "Tested Ubuntu version detected: ${PRETTY_NAME}"
  elif [[ "${ID:-}" == "ubuntu" ]]; then
    warn "This Ubuntu version has not been validated. Tested: Ubuntu Server 20.04 LTS and 22.04 LTS."
  else
    warn "This OS has not been validated. Tested: Ubuntu Server 20.04 LTS and 22.04 LTS."
  fi
else
  warn "Could not detect OS from /etc/os-release."
fi

# -----------------------------------------------------------------------------
# Required commands for execution
# -----------------------------------------------------------------------------

for cmd in git python3 pip3 docker tcpdump xz unxz ethtool ip iptables; do
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "Command available: $cmd"
  else
    fail "Missing command: $cmd"
  fi
done

# Open vSwitch commands
for cmd in ovs-vsctl ovs-ofctl; do
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "Open vSwitch command available: $cmd"
  else
    fail "Missing Open vSwitch command: $cmd"
  fi
done

# Optional command for PCAP inspection/conversion
if command -v tshark >/dev/null 2>&1; then
  ok "PCAP conversion command available: tshark"
else
  warn "tshark is missing. Topology execution can still work, but PCAP conversion/inspection may be limited."
fi

# -----------------------------------------------------------------------------
# Services
# -----------------------------------------------------------------------------

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
else
  warn "systemctl not available. Service status checks were skipped."
fi

# -----------------------------------------------------------------------------
# Docker daemon
# -----------------------------------------------------------------------------

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    ok "Docker daemon is reachable without sudo"
  elif sudo -v >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    ok "Docker daemon is reachable with sudo"
    warn "Docker requires sudo for this user. Log out/in or reboot if the installer added you to the docker group."
  else
    fail "Docker daemon is not reachable. Check service status and user permissions."
  fi
fi

# -----------------------------------------------------------------------------
# Python
# -----------------------------------------------------------------------------

if python3 -c "import sys; print(sys.version)" >/dev/null 2>&1; then
  ok "Python 3 is working"
else
  fail "Python 3 is not working"
fi

# Core Python packages
if python3 -c "import docker, pandas, paho.mqtt.client" >/dev/null 2>&1; then
  ok "Core Python packages available: docker, pandas, paho-mqtt"
else
  fail "Missing one or more core Python packages: docker, pandas, paho-mqtt"
fi

# Conversion/analysis Python packages
if python3 -c "import scapy" >/dev/null 2>&1; then
  ok "PCAP conversion package available: scapy"
else
  warn "Python package scapy is missing. PCAP conversion utilities may be limited."
fi

if python3 -c "import sklearn" >/dev/null 2>&1; then
  ok "Analysis package available: scikit-learn"
else
  warn "Python package scikit-learn is missing. Some analysis utilities may be limited."
fi

# -----------------------------------------------------------------------------
# Containernet import
# -----------------------------------------------------------------------------

if [[ -d "$CONTAINERNET_PATH" ]]; then
  ok "Containernet directory found: $CONTAINERNET_PATH"
else
  fail "Containernet directory not found: $CONTAINERNET_PATH"
fi

if sudo -v >/dev/null 2>&1; then
  if sudo env PYTHONPATH="$CONTAINERNET_PATH" python3 -c "from mininet.net import Containernet" >/dev/null 2>&1; then
    ok "Containernet import works through the run-script PYTHONPATH strategy"
  elif sudo python3 -c "from mininet.net import Containernet" >/dev/null 2>&1; then
    ok "Containernet import works with system Python"
  else
    fail "Containernet import failed. Install Containernet or set CONTAINERNET_PATH."
  fi
else
  fail "sudo validation failed. Containernet requires privileged execution."
fi

# -----------------------------------------------------------------------------
# Project files
# -----------------------------------------------------------------------------

for path in run_experiment.py demo_experiment.py devices scripts scripts/prepare_demo_data.sh sample_data/urban_observatory; do
  if [[ -e "$PROJECT_ROOT/$path" ]]; then
    ok "Project path found: $path"
  else
    fail "Missing project path: $path"
  fi
done

# -----------------------------------------------------------------------------
# Dataset checks
# -----------------------------------------------------------------------------

URBAN_XZ_COUNT=$(find "$PROJECT_ROOT/devices/urban_observatory" -type f \( -name "*.csv.xz" -o -name "*.csv" \) 2>/dev/null | wc -l | tr -d ' ')
if [[ "$URBAN_XZ_COUNT" -gt 0 ]]; then
  ok "Urban Observatory source datasets found: $URBAN_XZ_COUNT file(s)"
else
  warn "No Urban Observatory .csv/.csv.xz source files found. Minimal demo data preparation will fail until datasets are present."
fi

DEMO_CSV_COUNT=$(find "$PROJECT_ROOT/sample_data/urban_observatory" -type f -name "*.csv" 2>/dev/null | wc -l | tr -d ' ')
if [[ "$DEMO_CSV_COUNT" -gt 0 ]]; then
  ok "Generated minimal demo CSV files found: $DEMO_CSV_COUNT file(s)"
else
  warn "Minimal demo data not prepared. Run ./scripts/prepare_demo_data.sh --duration 120 --clean"
fi

DEVICE_DATASET_COUNT=$(find "$PROJECT_ROOT/devices" -type f \( -name "*.csv.xz" -o -name "*.txt.xz" -o -name "*.mp4" \) 2>/dev/null | wc -l | tr -d ' ')
if [[ "$DEVICE_DATASET_COUNT" -gt 0 ]]; then
  ok "Device dataset/video artifacts found: $DEVICE_DATASET_COUNT file(s)"
else
  warn "No compressed dataset/video artifacts found under devices/. Full image build may fail."
fi

# -----------------------------------------------------------------------------
# Demo Docker images
# -----------------------------------------------------------------------------

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  for image in myzoo/mqtt_broker myzoo/urban_sensor; do
    if docker image inspect "$image" >/dev/null 2>&1; then
      ok "Docker image available: $image"
    else
      warn "Docker image not found: $image. Run ./scripts/build_images.sh --demo"
    fi
  done
else
  warn "Skipping Docker image checks because Docker is not reachable without sudo."
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

printf "\nSummary: %s error(s), %s warning(s).\n" "$ERRORS" "$WARNINGS"

if [[ "$ERRORS" -gt 0 ]]; then
  exit 1
fi

exit 0