FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    bash \
    iproute2 \
    iputils-ping \
    ethtool \
    python3 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY consume.py /consume.py
RUN chmod +x /consume.py

CMD [ "python3", "-u", "/consume.py" ]
