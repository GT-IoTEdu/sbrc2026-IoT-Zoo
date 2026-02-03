FROM bluenviron/mediamtx:latest AS rtsp

FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    bash \
    iproute2 \
    iputils-ping \
    ethtool \
    && rm -rf /var/lib/apt/lists/*


COPY --from=rtsp /mediamtx /
COPY rtsp-simple-server.yml /mediamtx.yml

CMD [ "/mediamtx" ]
