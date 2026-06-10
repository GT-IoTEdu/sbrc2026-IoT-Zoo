ALLOW_UNSUPPORTED=false

if [[ "${1:-}" == "--allow-unsupported" ]]; then
  ALLOW_UNSUPPORTED=true
fi

if [[ -f /etc/os-release ]]; then
  . /etc/os-release
else
  echo "Cannot detect OS. /etc/os-release not found."
  exit 1
fi

if [[ "${ID}" != "ubuntu" || "${VERSION_ID}" != "20.04" ]]; then
  echo "Unsupported OS: ${PRETTY_NAME}."
  echo "Official target: Ubuntu Server 20.04 LTS."

  if [[ "$ALLOW_UNSUPPORTED" != true ]]; then
    echo
    echo "To continue anyway, run:"
    echo "  ./scripts/install_ubuntu_20_04.sh --allow-unsupported"
    echo
    echo "For other systems, install dependencies manually and run ./scripts/check_environment.sh."
    exit 1
  fi

  echo
  echo "WARNING: continuing on an unsupported OS."
  echo "Installation may fail or require manual fixes."
  echo
fi