FROM alpine:3.20

RUN apk add --no-cache \
    python3 \
    bash \
    curl \
    transmission-daemon \
    transmission-cli

WORKDIR /app

COPY bencode.py /app/
COPY generator.py /app/
COPY tracker.py /app/
COPY transmission_client.py /app/
COPY server.py /app/
COPY entrypoint.sh /app/

RUN chmod +x /app/entrypoint.sh

ENV DATA_DIR=/data \
    PUBLIC_HOST=auto \
    HTTP_PORT=8080 \
    PEER_PORT=51413 \
    FILE_SIZE_GB=5.0 \
    PIECE_SIZE_MB=4

EXPOSE 8080 51413 51413/udp

VOLUME ["/data"]

ENTRYPOINT ["/app/entrypoint.sh"]
