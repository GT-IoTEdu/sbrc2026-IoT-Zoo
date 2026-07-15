#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as a regular sudo-enabled user, not as root."
  exit 1
fi

if [[ ! -f /etc/os-release ]]; then
  echo "Cannot detect operating system. Recommended: Ubuntu Server 20.04 or 22.04 LTS."
  exit 1
fi

# shellcheck disable=SC1091
. /etc/os-release

if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "Warning: unsupported OS: ${PRETTY_NAME:-unknown}."
  echo "Recommended: Ubuntu Server 20.04 or 22.04 LTS. Continuing best-effort."
elif [[ "${VERSION_ID:-}" != "20.04" && "${VERSION_ID:-}" != "22.04" ]]; then
  echo "Warning: Ubuntu ${VERSION_ID:-unknown} is not officially validated."
  echo "Recommended: Ubuntu Server 20.04 or 22.04 LTS. Continuing best-effort."
fi

if grep -qi microsoft /proc/version 2>/dev/null; then
  echo "WSL/WSL2 detected. IoT-Zoo requires a Linux VM with Docker, Open vSwitch, and network namespaces."
  exit 1
fi

echo "Installing IoT-Zoo dependencies..."

sudo apt-get update

# Avoid interactive Wireshark/tshark prompts during installation.
echo "wireshark-common wireshark-common/install-setuid boolean true" | sudo debconf-set-selections || true

sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git \
  ansible \
  build-essential \
  ca-certificates \
  curl \
  docker.io \
  ethtool \
  iproute2 \
  iptables \
  net-tools \
  openvswitch-common \
  openvswitch-switch \
  python3 \
  python3-dev \
  python3-pip \
  python3-setuptools \
  tcpdump \
  tshark \
  xz-utils

sudo systemctl enable --now docker || true
sudo systemctl enable --now openvswitch-switch || true
sudo usermod -aG docker "$USER" || true

python3 -m pip install --user --upgrade pip
python3 -m pip install --user pandas paho-mqtt scapy scikit-learn pyyaml
# Some scripts run under sudo/root. Make the packages available there too.
sudo python3 -m pip install --upgrade pandas paho-mqtt scapy scikit-learn pyyaml

CONTAINERNET_DIR="${CONTAINERNET_PATH:-$HOME/containernet}"
if [[ ! -d "$CONTAINERNET_DIR/.git" ]]; then
  git clone https://github.com/containernet/containernet.git "$CONTAINERNET_DIR"
else
  echo "Containernet already exists at $CONTAINERNET_DIR"
fi

cd "$CONTAINERNET_DIR/ansible"
sudo ansible-playbook -i "localhost," -c local install.yml

cd "$CONTAINERNET_DIR"
sudo make install

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
chmod +x scripts/*.sh build_images.sh run_experiment.py demo_experiment.py topology_loader.py || true

cat <<MSG

Installation completed.

If this script added your user to the Docker group, reboot or close and reopen the terminal.
Then run:

  ./scripts/check_environment.sh
  ./scripts/prepare_demo_data.sh --duration 120 --clean
  ./scripts/build_images.sh --demo
  ./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_demo.pcap

To validate the configurable full topology without launching the network:

  ./scripts/run_full.sh --topology topology.yaml --dry-run

To run the configurable full topology:

  ./scripts/build_images.sh --full
  ./scripts/run_full.sh --time 600 --output /tmp/iot_zoo_full.pcap
MSG
