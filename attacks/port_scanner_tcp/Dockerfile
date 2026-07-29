FROM ubuntu:24.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        nmap bash iproute2 iputils-ping coreutils ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /iotzoo_attack
COPY entrypoint.sh /iotzoo_attack/entrypoint.sh
RUN chmod +x /iotzoo_attack/entrypoint.sh
CMD ["/bin/sh"]
