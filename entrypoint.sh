#!/usr/bin/env bash
set -e

DATA_DIR="${DATA_DIR:-/data}"
PUBLIC_HOST="${PUBLIC_HOST:-auto}"
HTTP_PORT="${HTTP_PORT:-8080}"
PEER_PORT="${PEER_PORT:-51413}"
FILE_SIZE_GB="${FILE_SIZE_GB:-5.0}"
PIECE_SIZE_MB="${PIECE_SIZE_MB:-4}"

echo "=================================================="
echo "    BitTorrent Speed Test - Container Starting    "
echo "=================================================="
echo "Data Directory:   ${DATA_DIR}"
echo "Public Host:      ${PUBLIC_HOST}"
echo "Web & Tracker:    Port ${HTTP_PORT}"
echo "Seeder Peer Port: Port ${PEER_PORT}"
echo "Test File Size:   ${FILE_SIZE_GB} GB"
echo "=================================================="

mkdir -p "${DATA_DIR}"
mkdir -p /app/transmission-config

# Configure Transmission Daemon
cat <<EOF > /app/transmission-config/settings.json
{
    "rpc-enabled": true,
    "rpc-port": 9091,
    "rpc-bind-address": "127.0.0.1",
    "rpc-whitelist-enabled": false,
    "rpc-authentication-required": false,
    "peer-port": ${PEER_PORT},
    "peer-port-random-on-start": false,
    "port-forwarding-enabled": false,
    "speed-limit-up-enabled": false,
    "speed-limit-down-enabled": false,
    "upload-slots-per-torrent": 256,
    "peer-limit-global": 500,
    "peer-limit-per-torrent": 250,
    "dht-enabled": false,
    "pex-enabled": false,
    "lpd-enabled": false,
    "utp-enabled": true,
    "download-dir": "${DATA_DIR}",
    "incomplete-dir-enabled": false,
    "ratio-limit-enabled": false,
    "idle-seeding-limit-enabled": false
}
EOF

# Start Transmission Daemon in background
echo "[*] Starting Transmission Seeder daemon..."
transmission-daemon -g /app/transmission-config --foreground --logfile /tmp/transmission.log &
TRANS_PID=$!

# Wait for Transmission RPC to be ready
echo "[*] Waiting for Transmission RPC..."
for i in $(seq 1 15); do
    if curl -s http://127.0.0.1:9091/transmission/rpc >/dev/null 2>&1 || [ $? -eq 409 ]; then
        echo "[+] Transmission RPC is ready."
        break
    fi
    sleep 1
done

# Generate test dummy data and .torrent if needed
export DATA_DIR="${DATA_DIR}"
export PUBLIC_HOST="${PUBLIC_HOST}"
export HTTP_PORT="${HTTP_PORT}"
export PEER_PORT="${PEER_PORT}"
export FILE_SIZE_GB="${FILE_SIZE_GB}"
export PIECE_SIZE_MB="${PIECE_SIZE_MB}"

echo "[*] Checking test payload and torrent..."
python3 /app/generator.py

echo "[+] Test payload and torrent checked."


# Trap to gracefully stop transmission on container exit
cleanup() {
    echo "[*] Container stopping, terminating transmission..."
    kill -TERM "${TRANS_PID}" 2>/dev/null || true
    wait "${TRANS_PID}" 2>/dev/null || true
}
trap cleanup SIGTERM SIGINT

# Start Web UI & Tracker server
echo "[*] Launching Web UI and BitTorrent Tracker on port ${HTTP_PORT}..."
python3 /app/server.py &
SERVER_PID=$!

wait "${SERVER_PID}"
cleanup
