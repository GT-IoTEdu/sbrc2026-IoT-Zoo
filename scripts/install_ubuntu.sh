#!/usr/bin/env bash
set -euo pipefail

echo "IoT-Zoo Ubuntu installer"
echo

if [[ -f /etc/os-release ]]; then
  . /etc/os-release
else
  echo "Warning: cannot detect OS because /etc/os-release was not found."
  echo "Make sure Docker, Open vSwitch, Containernet/Mininet, tcpdump, tshark, xz-utils and Python 3.8+ are available."
fi

if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "Warning: this installer was designed for Ubuntu-based systems."
  echo "Detected OS: ${PRETTY_NAME:-unknown}"
  echo "Tested environments: Ubuntu Server 20.04 LTS and Ubuntu Server 22.04 LTS."
  echo "If you continue on another system, make sure all required dependencies are available."
  echo
elif [[ "${VERSION_ID:-}" != "20.04" && "${VERSION_ID:-}" != "22.04" ]]; then
  echo "Warning: this Ubuntu version has not been validated."
  echo "Detected OS: ${PRETTY_NAME:-unknown}"
  echo "Tested environments: Ubuntu Server 20.04 LTS and Ubuntu Server 22.04 LTS."
  echo "If you continue, make sure all required dependencies are available."
  echo
else
  echo "Detected supported Ubuntu version: ${PRETTY_NAME}"
  echo
fi