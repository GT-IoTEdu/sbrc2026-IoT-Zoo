FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Toolchain de build + utilitários de rede para o Mininet/Containernet
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    python3 \
    libasio-dev \
    libtinyxml2-dev \
    ca-certificates \
    iputils-ping \
    iproute2 \
    net-tools \
    ethtool \
    && rm -rf /var/lib/apt/lists/*

# --- Compila o eProsima Micro-XRCE-DDS-Agent a partir do código fonte ---
# O superbuild baixa e compila as dependências (Fast CDR, etc.) automaticamente.
RUN git clone --depth 1 -b v2.4.3 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git /opt/Micro-XRCE-DDS-Agent \
    && cd /opt/Micro-XRCE-DDS-Agent \
    && mkdir build && cd build \
    && cmake -DUAGENT_BUILD_EXECUTABLE=ON .. \
    && make -j"$(nproc)" \
    && make install \
    && ldconfig

EXPOSE 8888/udp

# Remove o Entrypoint original para o Mininet assumir o controle.
# O agente é iniciado manualmente pelo run_experiment.py:
#   MicroXRCEAgent udp4 -p 8888 &
ENTRYPOINT ["/bin/bash"]
CMD []
