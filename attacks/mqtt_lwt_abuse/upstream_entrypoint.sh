#!/bin/sh
if [ "${#}" -eq 2 ]; then
	TARGET="${1}"
	PORT="${2}"
    set -e
    exec python3 /app/mqtt-lwt-abuse.py "${TARGET}" "${PORT}"
fi

