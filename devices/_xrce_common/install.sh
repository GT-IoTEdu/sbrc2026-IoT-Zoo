#!/usr/bin/env bash
# Instala a stack Micro-XRCE-DDS-Client (Micro-CDR + cliente) necessária para
# compilar o publicador genérico client_xrce.c. Adaptado de
# `ataques/attackers/xrce-dds-entity-flood/install.sh`.
set -e
export DEBIAN_FRONTEND=noninteractive

cd /opt/

# Micro-CDR (serialização CDR)
git clone --depth 1 https://github.com/eProsima/Micro-CDR.git
cd Micro-CDR
mkdir -p build && cd build
cmake ..
make -j"$(nproc)"
make install
ldconfig

# Micro-XRCE-DDS-Client
cd /opt/
rm -rf Micro-XRCE-DDS-Client
git clone --depth 1 https://github.com/eProsima/Micro-XRCE-DDS-Client.git
cd Micro-XRCE-DDS-Client
mkdir -p build && cd build
cmake .. -DUCLIENT_BUILD_EXAMPLES=OFF
make -j"$(nproc)"
make install
ldconfig
