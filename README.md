# BitTorrent Speed Test Container

A containerized, self-hosted BitTorrent speed test platform. It packages a **5 GB non-compressible dummy payload generator**, an **embedded BitTorrent HTTP tracker**, a **modern Web UI**, and an **uncapped Transmission seeder daemon** into a single lightweight image.

Designed for testing and saturating high-bandwidth network pipes (e.g. 1 Gbps – 10 Gbps) on public cloud VPS servers (such as `fio.ie`).

---

## Architecture & Data Flow

### System Components

```mermaid
flowchart LR
    subgraph ClientHost["User Workstation"]
        Browser["Web Browser"]
        TorrentClient["BitTorrent Client (e.g. qBittorrent)"]
    end

    subgraph Container["Podman Container (torrent-speedtest)"]
        subgraph WebStack["Python Web & Tracker Service (:8080)"]
            WebUI["Web Dashboard (HTML / JS)"]
            Tracker["HTTP Tracker (/announce, BEP 0003)"]
            StatsAPI["Telemetry API (/api/stats)"]
        end

        subgraph SeederDaemon["Transmission Headless Daemon"]
            Seeder["Transmission Engine (:51413 TCP/UDP)"]
            RPC["Transmission JSON-RPC (:9091)"]
        end

        subgraph Storage["Persistent Volume (/data)"]
            DummyFile["speedtest-5gb.bin (5 GB)"]
            TorrentFile["speedtest-5gb.torrent"]
        end
    end

    Browser -->|"1. Download .torrent / Magnet (:8080)"| WebUI
    Browser -.->|"Live Bandwidth Telemetry (:8080)"| StatsAPI
    StatsAPI <-->|"Poll Transfer Stats"| RPC
    TorrentClient -->|"2. Tracker Announce (:8080)"| Tracker
    Tracker -.->|"Returns Seeder IP & Port"| TorrentClient
    TorrentClient <===>|"3. Full-Speed Piece Transfer (:51413 TCP/UDP)"| Seeder
    Seeder -->|"Read Blocks"| DummyFile
```

---

### Speed Test Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as User
    participant Browser as Browser
    participant Client as BitTorrent Client
    participant Tracker as Python Tracker (:8080)
    participant Seeder as Transmission (:51413)

    User->>Browser: Visit http://<VPS_IP>:8080/
    Browser->>Tracker: GET /speedtest-5gb.torrent
    Tracker-->>Browser: Dynamic .torrent with current Host announce URL
    User->>Client: Open downloaded .torrent / Magnet
    Client->>Tracker: GET /announce?info_hash=...&peer_id=...&left=5368709120&compact=1
    Tracker-->>Client: Bencoded Response: [Seeder Public IP + Port 51413]
    Client->>Seeder: TCP/uTP Handshake + Bitfield Exchange
    loop High-Speed Transfer
        Client->>Seeder: Request Piece Chunks (4 MB blocks)
        Seeder-->>Client: Data Payload Chunks (Saturates Connection)
    end
    Client->>Tracker: GET /announce?event=completed&left=0
    Tracker-->>Client: Acknowledged
    Note over Client: User observes download speed graph
    Browser->>Tracker: GET /api/stats (Real-time live telemetry)
    Tracker-->>Browser: Updated Upload Speed & Active Leechers
```

---

### Startup & Priming Lifecycle

```mermaid
flowchart TD
    Start(["Container Boot (entrypoint.sh)"]) --> LoadEnv["Read Environment Variables (PUBLIC_HOST, FILE_SIZE_GB, etc.)"]
    LoadEnv --> StartTrans["Start Transmission Daemon (Uncapped, DHT disabled)"]
    StartTrans --> WaitRPC{"Wait for RPC (:9091) Ready"}
    WaitRPC -- Waiting --> WaitRPC
    WaitRPC -- Ready --> CheckFiles{"/data/speedtest-5gb.bin exists?"}

    CheckFiles -- No --> GenFile["Generate 5 GB Pseudo-Random Data (~15s)"]
    GenFile --> HashPieces["Compute SHA-1 Hashes (1280 x 4MB pieces)"]
    HashPieces --> WriteTorrent["Write speedtest-5gb.torrent & Metadata"]
    WriteTorrent --> PrimeTrans["Add Torrent to Transmission via JSON-RPC"]

    CheckFiles -- Yes --> LoadMeta["Load Existing Metadata"]
    LoadMeta --> PrimeTrans

    PrimeTrans --> VerifyTorrent["Verify Local 100% Integrity & Start Seeding"]
    VerifyTorrent --> DetectIP["Detect Public IPv4 (or resolve PUBLIC_HOST)"]
    DetectIP --> LaunchServer["Launch Python Web UI & Tracker (:8080)"]
    LaunchServer --> Ready(["Container Ready for Speed Tests"])
```

---

## Features

- **Real 5 GB Test Payload**: On first startup, generates a real 5 GB file composed of non-compressible pseudo-random byte patterns (generated in ~15 seconds, hashes cached).
- **Private BitTorrent Flag**: Ensures BitTorrent clients only connect directly to your test server without advertising on DHT or PEX.
- **Embedded Python HTTP Tracker**: Implements BEP 0003 compact peer format, automatically directing downloading clients to the container's public IP and seeder port.
- **Dynamic Announce URL Injection**: When a user downloads `/speedtest-5gb.torrent`, the server dynamically tailors the announce URL to the client's connection host or configured `PUBLIC_HOST`.
- **Integrated Seeder Daemon**: Pre-tuned headless Transmission instance running in the background with uncapped upload bandwidth, 256 upload slots, and high peer limits.
- **Modern Responsive Web UI**: Dark mode dashboard displaying live seeder upload speed (MB/s and Mbps), cumulative data transferred, and active leecher count.
- **Podman & Docker Native**: Built on Alpine Linux with zero third-party Python dependencies (runs on pure Python 3 standard library).

---

## Ports Required

Ensure the following ports are open on your VPS firewall (e.g., `ufw`, `iptables`, cloud security group):

| Port | Protocol | Purpose |
|---|---|---|
| **8080** | TCP | Web UI & BitTorrent HTTP Tracker (`/announce`) |
| **51413** | TCP & UDP | BitTorrent peer wire transfer (Transmission Seeder) |

---

## Quick Start (Podman)

### 1. Build the Image

```bash
podman build -t torrent-speedtest .
```

### 2. Run the Container

#### With Auto-Detected Public IP:
```bash
podman run -d \
  --name torrent-speedtest \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 51413:51413 \
  -p 51413:51413/udp \
  -v torrent_data:/data \
  torrent-speedtest
```

#### With Custom Domain / VPS IP:
```bash
podman run -d \
  --name torrent-speedtest \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 51413:51413 \
  -p 51413:51413/udp \
  -e PUBLIC_HOST=speedtest.fio.ie \
  -v torrent_data:/data \
  torrent-speedtest
```

---

## Running with Podman Compose / Docker Compose

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

Start the service:

```bash
podman-compose up -d
# or: docker compose up -d
```

---

## Configuration Options

Set these environment variables when running the container:

| Variable | Default | Description |
|---|---|---|
| `PUBLIC_HOST` | `auto` | Public IP or domain name of your VPS. If `auto`, the container queries external IP APIs (`ipify`, `ifconfig.me`) on boot. |
| `HTTP_PORT` | `8080` | Port for the Web UI and HTTP tracker announce endpoint. |
| `PEER_PORT` | `51413` | Port for Transmission peer connections (TCP & UDP). |
| `FILE_SIZE_GB` | `5.0` | Size in GB of the dummy test payload. |
| `PIECE_SIZE_MB` | `4` | Piece size in MB for the `.torrent` file. |
| `DATA_DIR` | `/data` | Directory where the test binary and `.torrent` file are stored. |

---

## How to Run a Speed Test

1. Open your browser and navigate to `http://<YOUR_VPS_IP_OR_HOST>:8080`.
2. Click **Download 5GB .torrent** (or copy the **Magnet Link**).
3. Open the torrent file in any client (such as [qBittorrent](https://www.qbittorrent.org/), [Transmission](https://transmissionbt.com/), etc.).
4. The client will announce to your container's tracker and immediately connect to the seeder.
5. Watch your client download speed ramp up to saturate your downstream connection.
6. Check the container Web UI to see real-time seeder upload rate and active leechers.
