#!/usr/bin/env bash
# Compila o publicador genérico DDS-XRCE. Adaptado de
# `ataques/attackers/xrce-dds-entity-flood/compile.sh`.
set -e

# As libs eProsima (Micro-CDR / Micro-XRCE-DDS-Client) instalam em prefixos
# VERSIONADOS dentro de /usr/local (ex.: /usr/local/microcdr-2.0.2/include e
# .../lib), e não diretamente em /usr/local/include. Descobrimos esses
# diretórios dinamicamente para montar as flags de include/link.
INCS="-I/usr/local/include"
LIBS="-L/usr/local/lib"
for d in $(find /usr/local -maxdepth 2 -type d -name include 2>/dev/null); do
    INCS="$INCS -I$d"
done
for d in $(find /usr/local -maxdepth 2 -type d -name lib 2>/dev/null); do
    LIBS="$LIBS -L$d"
done

DDS_CFLAGS="-Wall -Wextra -O2 $INCS"
DDS_LIBS="$LIBS -lmicroxrcedds_client -lmicrocdr -lpthread"

gcc /opt/client_xrce.c -o /usr/local/bin/client_xrce ${DDS_CFLAGS} ${DDS_LIBS}
chmod +x /usr/local/bin/client_xrce
echo "[xrce] client_xrce compilado em /usr/local/bin/client_xrce"
