FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Toolchain de build + utilitários de rede para o Mininet/Containernet
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    pkg-config \
    ca-certificates \
    iputils-ping \
    iproute2 \
    net-tools \
    ethtool \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Compila a stack Micro-XRCE-DDS-Client
COPY devices/_xrce_common/install.sh /opt/install.sh
RUN chmod +x /opt/install.sh && /opt/install.sh

# Compila o publicador genérico dirigido por dataset
COPY devices/_xrce_common/client_xrce.c /opt/client_xrce.c
COPY devices/_xrce_common/compile.sh /opt/compile.sh
RUN chmod +x /opt/compile.sh && /opt/compile.sh

# O dataset de cada device é montado em /dataset.csv via volume no run_experiment.py.
# Parâmetros (agent, topic, dataset, sleep) são passados como argumentos na execução.
CMD ["/bin/bash"]
