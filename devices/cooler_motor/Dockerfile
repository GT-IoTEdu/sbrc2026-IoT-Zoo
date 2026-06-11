FROM ubuntu:focal

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    sntp \
    python3 \
    python3-pip \
    wget \
    ca-certificates \
    openssh-server \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir paho-mqtt==1.6.1 eclipse-zenoh==1.7.2

# Cria dados dummy (já que não temos o xz original)
RUN echo "timestamp,x,y,z" > /accelerometer.csv && \
    for i in $(seq 1 100); do echo "$i,0.1,0.2,0.3" >> /accelerometer.csv; done && \
    xz /accelerometer.csv

# AQUI ESTÁ A MÁGICA: Trazendo de volta a cópia dos certificados
COPY --from=iotsim/certificates:latest /artifacts/pki/iot-sim-ca.crt /iot-sim-ca.crt

COPY client.py /client.py
COPY client_zenoh.py /client_zenoh.py
COPY iotzoo_zenoh.py /iotzoo_zenoh.py
RUN chmod +x /client.py

ENTRYPOINT ["/client.py"]
