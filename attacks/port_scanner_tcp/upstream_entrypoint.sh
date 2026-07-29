#!/usr/bin/env bash
if [ "${#}" -eq 1 ]; then
	TARGET="${1}"
    /usr/bin/nmap -sT "${TARGET}"
fi
