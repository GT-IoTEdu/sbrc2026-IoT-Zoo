FROM ubuntu:focal

RUN apt update && apt install -y --no-install-recommends \
    iputils-ping \
    sntp \
    python3 \
    python3-pip \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Opcional: deixar vulnerável a Mirai, como no building (telnet via busybox)
RUN wget https://busybox.net/downloads/binaries/1.35.0-x86_64-linux-musl/busybox && \
    chmod +x busybox && \
    mv busybox /bin && \
    printf '#!/bin/sh\n/bin/busybox sh\n' > /bin/busyboxsh && \
    chmod +x /bin/busyboxsh

RUN pip3 install --no-cache-dir paho-mqtt==1.6.1

# Copia todos os subjects para dentro da imagem
# Estrutura esperada no host:
#   mhealth/
#     mHealth_subject1.log
#     ...
#     mHealth_subject10.log
COPY mhealth/ /mhealth/

# Certificado da CA (se você já usa esse estágio em outros devices)
COPY --from=iotsim/certificates:latest /artifacts/pki/iot-sim-ca.crt /iot-sim-ca.crt

COPY client.py /client.py
RUN chmod +x /client.py

ENTRYPOINT ["/client.py"]
