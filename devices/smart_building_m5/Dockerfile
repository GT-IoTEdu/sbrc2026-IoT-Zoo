FROM ubuntu:focal

RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    iproute2 \
    net-tools \
    ethtool \
    sntp \
    python3 \
    python3-pip \
    wget \
    ca-certificates \
    openssh-server \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://busybox.net/downloads/binaries/1.35.0-x86_64-linux-musl/busybox &&\
    chmod +x busybox &&\
    mv busybox /bin &&\
    printf '#!/bin/sh\n/bin/busybox sh\n' > /bin/busyboxsh &&\
    chmod +x /bin/busyboxsh

RUN pip3 install --no-cache-dir paho-mqtt==1.6.1

COPY dataset/dataset.csv.xz /dataset.csv.xz
COPY --from=iotsim/certificates:latest /artifacts/pki/iot-sim-ca.crt /iot-sim-ca.crt
COPY client.py /client.py

RUN chmod +x /client.py

CMD ["/bin/bash"]
