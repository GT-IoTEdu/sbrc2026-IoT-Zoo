FROM ubuntu:24.04

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 python3-pip bash iproute2 iputils-ping coreutils ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /iotzoo_attack
COPY requirements.txt /iotzoo_attack/requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /iotzoo_attack/requirements.txt

COPY mqtt-qos-amplification.py /iotzoo_attack/mqtt-qos-amplification.py
COPY entrypoint.sh /iotzoo_attack/entrypoint.sh
RUN chmod +x /iotzoo_attack/entrypoint.sh

# Keep the container passive at creation time. run_experiment.py starts the
# attack after Containernet attaches the L3 interface and routes.
CMD ["/bin/sh"]
