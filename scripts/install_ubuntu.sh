#!/usr/bin/env bash
set -euo pipefail

echo "IoT-Zoo Ubuntu installer"
echo

# -----------------------------------------------------------------------------
# OS detection
# -----------------------------------------------------------------------------

if [[ -f /etc/os-release ]]; then
  . /etc/os-release
else
  echo "[WARN] Cannot detect OS because /etc/os-release was not found."
  echo "[WARN] Make sure Docker, Open vSwitch, Containernet/Mininet, tcpdump, tshark,"
  echo "       xz-utils and Python 3.8+ are available."
  echo
fi

if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "[WARN] This installer was designed for Ubuntu-based systems."
  echo "[WARN] Detected OS: ${PRETTY_NAME:-unknown}"
  echo "[WARN] Tested environments: Ubuntu Server 20.04 LTS and Ubuntu Server 22.04 LTS."
  echo "[WARN] If you continue on another system, make sure all required dependencies are available."
  echo
elif [[ "${VERSION_ID:-}" != "20.04" && "${VERSION_ID:-}" != "22.04" ]]; then
  echo "[WARN] This Ubuntu version has not been validated."
  echo "[WARN] Detected OS: ${PRETTY_NAME:-unknown}"
  echo "[WARN] Tested environments: Ubuntu Server 20.04 LTS and Ubuntu Server 22.04 LTS."
  echo "[WARN] The script will continue, but installation may require manual fixes."
  echo
else
  echo "[OK] Detected tested Ubuntu version: ${PRETTY_NAME}"
  echo
fi

# -----------------------------------------------------------------------------
# System dependencies
# -----------------------------------------------------------------------------

echo "[1/6] Updating package lists..."
sudo apt-get update

echo "[2/6] Installing system dependencies..."
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git \
  curl \
  wget \
  ca-certificates \
  gnupg \
  lsb-release \
  software-properties-common \
  ansible \
  python3 \
  python3-pip \
  python3-setuptools \
  python3-dev \
  build-essential \
  iproute2 \
  iptables \
  ethtool \
  tcpdump \
  tshark \
  xz-utils \
  openvswitch-switch \
  openvswitch-common

# -----------------------------------------------------------------------------
# Docker
# -----------------------------------------------------------------------------

echo "[3/6] Installing Docker Engine if needed..."

if command -v docker >/dev/null 2>&1; then
  echo "[OK] Docker is already installed."
else
  echo "[INFO] Docker not found. Installing Docker using the official convenience script..."
  curl -fsSL https://get.docker.com | sudo sh
fi

echo "[INFO] Enabling Docker service..."
sudo systemctl enable --now docker

if groups "$USER" | grep -q '\bdocker\b'; then
  echo "[OK] User $USER already belongs to the docker group."
else
  echo "[INFO] Adding user $USER to the docker group..."
  sudo usermod -aG docker "$USER"
  echo "[WARN] You must log out and log in again, or reboot, for Docker group permissions to take effect."
fi

# -----------------------------------------------------------------------------
# Open vSwitch
# -----------------------------------------------------------------------------

echo "[4/6] Enabling Open vSwitch..."
sudo systemctl enable --now openvswitch-switch || {
  echo "[WARN] Could not enable openvswitch-switch via systemctl."
  echo "[WARN] Please check the Open vSwitch installation manually if the environment check fails."
}

# -----------------------------------------------------------------------------
# Python dependencies
# -----------------------------------------------------------------------------

echo "[5/6] Installing Python dependencies..."

python3 -m pip install --user --upgrade pip

python3 -m pip install --user \
  docker \
  pandas \
  paho-mqtt \
  scapy \
  scikit-learn

# -----------------------------------------------------------------------------
# Containernet
# -----------------------------------------------------------------------------

echo "[6/6] Installing Containernet..."

CONTAINERNET_DIR="${CONTAINERNET_PATH:-$HOME/containernet}"

if [[ -d "$CONTAINERNET_DIR" ]]; then
  echo "[INFO] Containernet directory already exists at: $CONTAINERNET_DIR"
  echo "[INFO] Skipping clone. To reinstall, remove this directory and run the installer again."
else
  git clone https://github.com/containernet/containernet.git "$CONTAINERNET_DIR"
fi

if [[ ! -d "$CONTAINERNET_DIR/ansible" ]]; then
  echo "[ERROR] Containernet ansible directory not found: $CONTAINERNET_DIR/ansible"
  echo "[ERROR] Remove $CONTAINERNET_DIR and run this installer again."
  exit 1
fi

cd "$CONTAINERNET_DIR/ansible"
sudo ansible-playbook -i "localhost," -c local install.yml

cd "$CONTAINERNET_DIR"
sudo make install

# -----------------------------------------------------------------------------
# Final message
# -----------------------------------------------------------------------------

echo
echo "Installation finished."
echo
echo "Next steps:"
echo "  1. If your user was added to the docker group, close and reopen the terminal,"
echo "     log out and log in again, or reboot the VM."
echo
echo "  2. From the IoT-Zoo project directory, run:"
echo "       ./scripts/check_environment.sh"
echo
echo "  3. Then run the minimal demo workflow:"
echo "       ./scripts/prepare_demo_data.sh --duration 120 --clean"
echo "       ./scripts/build_images.sh --demo"
echo "       ./scripts/run_demo.sh --time 120 --output /tmp/iot_zoo_demo.pcap"
echo