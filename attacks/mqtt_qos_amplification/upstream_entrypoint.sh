#!/bin/sh
if [ "${#}" -eq 2 ]; then
	TARGET="${1}"
	PORT="${2}"
    set -e
    exec python3 /app/mqtt-qos-amplification.py "${TARGET}" "${PORT}"
fi

