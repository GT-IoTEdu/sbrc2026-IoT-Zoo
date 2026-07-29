#!/usr/bin/env bash
if [ "${#}" -eq 1 ]; then
    TARGET="${1}"
    fping -q -g -t 30 -r 1 "${TARGET}"
fi
