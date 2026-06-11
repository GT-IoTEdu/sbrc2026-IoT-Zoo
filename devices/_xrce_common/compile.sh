#!/usr/bin/env bash
# Compila o publicador genérico DDS-XRCE. Adaptado de
# `ataques/attackers/xrce-dds-entity-flood/compile.sh`.
set -e

DDS_CFLAGS="-Wall -Wextra -O2 -I/usr/local/include"
DDS_LIBS="-L/usr/local/lib -lmicroxrcedds_client -lmicrocdr -lpthread"

gcc /opt/client_xrce.c -o /usr/local/bin/client_xrce ${DDS_CFLAGS} ${DDS_LIBS}
chmod +x /usr/local/bin/client_xrce
echo "[xrce] client_xrce compilado em /usr/local/bin/client_xrce"
