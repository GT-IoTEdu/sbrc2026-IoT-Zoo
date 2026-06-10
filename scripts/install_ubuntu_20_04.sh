#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this script as a regular sudo-enabled user, not as root."
  exit 1
fi

if [[ ! -f /etc/os-release ]]; then
  echo "Cannot detect operating system. Expected Ubuntu Server 20.04 LTS."
  exit 1
fi

# shellcheck disable=SC1091
. /etc/os-release

if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "20.04" ]]; then
  echo "Unsupported OS: ${PRETTY_NAME:-unknown}."
  echo "Official target: Ubuntu Server 20.04 LTS."
  echo "For other systems, install dependencies manually and run ./scripts/check_environment.sh."
  exit 1
fi

echo "Installing IoT-Zoo dependencies for Ubuntu 20.04 LTS..."

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
  openvswitch-switch \
  python3 \
  python3-pip \
  tcpdump \
  tshark \
  xz-utils

sudo systemctl enable --now docker || true
sudo systemctl enable --now openvswitch-switch || true

sudo usermod -aG docker "$USER" || true

python3 -m pip install --user --upgrade pip
python3 -m pip install --user pandas paho-mqtt scapy

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

cat <<MSG

Installation completed.

If this script added your user to the Docker group, close and reopen the terminal.
Then run:

  ./scripts/check_environment.sh
  ./scripts/prepare_demo_data.sh --duration 120 --clean
  ./scripts/build_images.sh --demo
  ./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_demo.pcap
MSG
