#!/usr/bin/env bash
if [ "${#}" -eq 2 ]; then
	TARGET="${1}"
    PORT="${2}"
    COUNT="${COUNT:-0}"
    RATE_PPS="${RATE_PPS:-${RATE:-0}}"
    DURATION_S="${DURATION_S:-0}"
    PAYLOAD_SIZE="${PAYLOAD_SIZE:-0}"

    cmd=(hping3 -2 -p "${PORT}")
    if [ "${PAYLOAD_SIZE}" -gt 0 ]; then
        cmd+=(-d "${PAYLOAD_SIZE}")
    fi
    if [ "${COUNT}" -gt 0 ]; then
        cmd+=(-c "${COUNT}")
    fi
    if [ "${RATE_PPS}" -gt 0 ]; then
        interval_us=$((1000000 / RATE_PPS))
        if [ "${interval_us}" -lt 1 ]; then
            interval_us=1
        fi
        cmd+=(-i "u${interval_us}")
    else
        cmd+=(--flood)
    fi
    cmd+=("${TARGET}")

    if [ "${DURATION_S}" -gt 0 ]; then
        timeout "${DURATION_S}" "${cmd[@]}"
    else
        "${cmd[@]}"
    fi
fi
