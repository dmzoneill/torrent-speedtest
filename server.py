"""
Unified Web UI and BitTorrent Tracker Server for Torrent Speed Test.
"""
import http.server
import json
import os
import re
import socket
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

import bencode
from tracker import Tracker
from transmission_client import TransmissionClient

# Embedded Web UI HTML
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BitTorrent Speed Test</title>
    <style>
        :root {
            --bg-base: #0f172a;
            --bg-surface: #1e293b;
            --bg-card: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-primary: #38bdf8;
            --accent-hover: #0284c7;
            --success: #22c55e;
            --warning: #f59e0b;
            --border: #475569;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-primary);
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            padding: 2rem 1rem;
        }

        .container {
            max-width: 860px;
            width: 100%;
        }

        header {
            text-align: center;
            margin-bottom: 2.5rem;
        }

        header h1 {
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }

        header p {
            color: var(--text-secondary);
            font-size: 1.1rem;
        }

        .card {
            background-color: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.75rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }

        .actions {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            margin-top: 1rem;
        }

        @media (min-width: 640px) {
            .actions {
                flex-direction: row;
            }
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            padding: 0.9rem 1.75rem;
            font-size: 1.05rem;
            font-weight: 600;
            border-radius: 8px;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
            border: none;
            flex: 1;
        }

        .btn-primary {
            background-color: var(--accent-primary);
            color: #0f172a;
        }

        .btn-primary:hover {
            background-color: var(--accent-hover);
            color: #ffffff;
            transform: translateY(-1px);
        }

        .btn-secondary {
            background-color: var(--bg-card);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background-color: #475569;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }

        .stat-item {
            background-color: var(--bg-card);
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
        }

        .stat-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.35rem;
        }

        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        .stat-unit {
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: normal;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.25rem 0.65rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
        }

        .badge-online {
            background-color: rgba(34, 197, 94, 0.15);
            color: var(--success);
            border: 1px solid rgba(34, 197, 94, 0.3);
        }

        .pulse {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--success);
            box-shadow: 0 0 8px var(--success);
        }

        ol {
            padding-left: 1.25rem;
            margin-top: 0.75rem;
            color: var(--text-secondary);
            line-height: 1.8;
        }

        ol li strong {
            color: var(--text-primary);
        }

        code {
            background-color: var(--bg-card);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-size: 0.9rem;
            color: var(--accent-primary);
            word-break: break-all;
        }

        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 0.9rem;
        }

        .info-row:last-child {
            border-bottom: none;
        }

        .copy-feedback {
            font-size: 0.85rem;
            color: var(--success);
            margin-top: 0.5rem;
            display: none;
            text-align: center;
        }

        footer {
            margin-top: 2rem;
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Torrent Speed Test</h1>
            <p>Self-hosted Peer-to-Peer Bandwidth & Saturation Benchmark</p>
        </header>

        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2>Test Torrent File</h2>
                <div class="badge badge-online">
                    <div class="pulse"></div>
                    <span>Seeder Active</span>
                </div>
            </div>
            <p style="color: var(--text-secondary); margin-top: 0.5rem;">
                Download the <strong>5 GB</strong> dummy torrent or import via Magnet link into any standard client (qBittorrent, Transmission, Deluge, etc.).
            </p>

            <div class="actions">
                <a href="/speedtest-5gb.torrent" class="btn btn-primary" id="download-torrent-btn">
                    <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                    </svg>
                    Download 5GB .torrent
                </a>
                <button class="btn btn-secondary" onclick="copyMagnet()">
                    <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path>
                    </svg>
                    Copy Magnet Link
                </button>
            </div>
            <div id="copy-feedback" class="copy-feedback">Magnet URI copied to clipboard!</div>
        </div>

        <div class="card">
            <h2>Live Server & Seeder Telemetry</h2>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-label">Current Seeding Speed</div>
                    <div class="stat-value" id="stat-speed">0.0 <span class="stat-unit">MB/s</span></div>
                    <div class="stat-unit" id="stat-speed-mbps" style="margin-top: 0.2rem;">0 Mbps</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Total Uploaded</div>
                    <div class="stat-value" id="stat-uploaded">0.0 <span class="stat-unit">GB</span></div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Active Leechers</div>
                    <div class="stat-value" id="stat-leechers">0</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Piece Size</div>
                    <div class="stat-value">4 <span class="stat-unit">MiB</span></div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Instructions</h2>
            <ol>
                <li>Click <strong>Download 5GB .torrent</strong> or copy the Magnet Link.</li>
                <li>Open your BitTorrent client and add the torrent.</li>
                <li>Verify the tracker status shows <code>Working / OK</code>.</li>
                <li>Observe your client's maximum download speed graph as it saturates the connection!</li>
                <li>When the download finishes, remove the dummy file from your disk.</li>
            </ol>
        </div>

        <div class="card">
            <h2>Network & Configuration Details</h2>
            <div class="info-row">
                <span style="color: var(--text-secondary);">Public Seeder IP / Host</span>
                <code id="info-host">Loading...</code>
            </div>
            <div class="info-row">
                <span style="color: var(--text-secondary);">Tracker Announce URL</span>
                <code id="info-announce">Loading...</code>
            </div>
            <div class="info-row">
                <span style="color: var(--text-secondary);">BitTorrent Peer Port</span>
                <code>51413 (TCP/UDP)</code>
            </div>
            <div class="info-row">
                <span style="color: var(--text-secondary);">Torrent Info Hash</span>
                <code id="info-hash">Loading...</code>
            </div>
        </div>

        <footer>
            Containerized BitTorrent Speed Test &bull; Powered by Python & Transmission
        </footer>
    </div>

    <script>
        let currentMagnet = "";

        function formatBytes(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        async function updateStats() {
            try {
                const res = await fetch('/api/stats');
                if (!res.ok) return;
                const data = await res.json();

                // Speeds
                const speedBytes = data.transmission?.uploadSpeed || 0;
                const speedMB = (speedBytes / (1024 * 1024)).toFixed(2);
                const speedMbps = ((speedBytes * 8) / 1000000).toFixed(1);
                document.getElementById('stat-speed').innerHTML = `${speedMB} <span class="stat-unit">MB/s</span>`;
                document.getElementById('stat-speed-mbps').textContent = `${speedMbps} Mbps`;

                // Total uploaded
                const totalBytes = data.transmission?.['cumulative-stats']?.uploadedBytes || 0;
                const totalGB = (totalBytes / (1024 * 1024 * 1024)).toFixed(2);
                document.getElementById('stat-uploaded').innerHTML = `${totalGB} <span class="stat-unit">GB</span>`;

                // Leechers & Peers
                const leechers = data.tracker?.active_leechers || 0;
                document.getElementById('stat-leechers').textContent = leechers;

                // Host & Info
                document.getElementById('info-host').textContent = data.network?.public_host || window.location.hostname;
                document.getElementById('info-announce').textContent = data.network?.announce_url || (window.location.origin + '/announce');
                document.getElementById('info-hash').textContent = data.metadata?.info_hash_hex || 'N/A';

                currentMagnet = data.metadata?.magnet_uri || '';
            } catch (err) {
                console.error('Failed to fetch stats:', err);
            }
        }

        function copyMagnet() {
            if (!currentMagnet) return;
            navigator.clipboard.writeText(currentMagnet).then(() => {
                const feedback = document.getElementById('copy-feedback');
                feedback.style.display = 'block';
                setTimeout(() => {
                    feedback.style.display = 'none';
                }, 3000);
            });
        }

        updateStats();
        setInterval(updateStats, 2000);
    </script>
</body>
</html>
"""


def parse_tracker_query(raw_query: str) -> Dict[str, bytes]:
    """Parse query string while preserving raw bytes (critical for info_hash and peer_id)."""
    params: Dict[str, bytes] = {}
    for part in raw_query.split("&"):
        if not part:
            continue
        k_v = part.split("=", 1)
        k = urllib.parse.unquote(k_v[0])
        raw_val = k_v[1] if len(k_v) > 1 else ""
        val_bytes = urllib.parse.unquote_to_bytes(raw_val)
        params[k] = val_bytes
    return params


def detect_public_ip() -> str:
    """Attempt auto-detection of public IP from external service."""
    endpoints = ["https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"]
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                ip = resp.read().decode("utf-8").strip()
                if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                    return ip
        except Exception:
            continue
    return "127.0.0.1"


class SpeedtestServer:
    def __init__(
        self,
        data_dir: str = "/data",
        http_host: str = "0.0.0.0",
        http_port: int = 8080,
        public_host: Optional[str] = None,
        seeder_port: int = 51413,
        transmission_rpc_url: str = "http://127.0.0.1:9091/transmission/rpc",
    ):
        self.data_dir = data_dir
        self.http_host = http_host
        self.http_port = http_port
        self.seeder_port = seeder_port
        self.transmission = TransmissionClient(transmission_rpc_url)

        # Resolve public host/IP
        if not public_host or public_host.lower() in ("auto", "0.0.0.0"):
            print("[*] Detecting public IP...")
            self.public_host = detect_public_ip()
            print(f"[+] Detected public IP: {self.public_host}")
        else:
            self.public_host = public_host

        # Resolve IPv4 for tracker peer list
        try:
            self.seeder_ip = socket.gethostbyname(self.public_host)
        except socket.error:
            self.seeder_ip = self.public_host

        print(f"[*] Initialized Seeder at {self.seeder_ip}:{self.seeder_port}")
        self.tracker = Tracker(seeder_ip=self.seeder_ip, seeder_port=self.seeder_port)
        self.load_metadata()
        self.ensure_seeding()

    def load_metadata(self):
        meta_path = os.path.join(self.data_dir, "speedtest-info.json")
        self.metadata = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            except Exception as e:
                print(f"[!] Warning: Failed reading {meta_path}: {e}")

    def ensure_seeding(self):
        """Ensures the speed test torrent is added and seeding in Transmission."""
        torrent_file = self.metadata.get("torrent_file")
        if not torrent_file or not os.path.exists(torrent_file):
            return
        try:
            torrents = self.transmission.get_torrents()
            if not torrents:
                print("[*] Adding torrent to Transmission via RPC...")
                self.transmission.add_torrent(torrent_file, self.data_dir)
                time.sleep(1)
                self.transmission.verify_all()
                self.transmission.start_all()
                print("[+] Torrent added and primed in Transmission.")
        except Exception as e:
            print(f"[!] Warning during Transmission prime: {e}")


    def get_dynamic_torrent_bytes(self, client_host: str) -> bytes:
        """Returns .torrent bytes with announce URL adjusted to the requested Host."""
        torrent_file = self.metadata.get("torrent_file")
        if not torrent_file or not os.path.exists(torrent_file):
            return b""

        with open(torrent_file, "rb") as f:
            raw = f.read()

        try:
            torrent_dict = bencode.bdecode(raw)
            # Use public_host if set to real domain/IP, otherwise use incoming request Host header
            effective_host = self.public_host if self.public_host not in ("127.0.0.1", "localhost") else client_host
            if ":" not in effective_host and self.http_port not in (80, 443):
                announce_host = f"{effective_host}:{self.http_port}"
            else:
                announce_host = effective_host

            torrent_dict["announce"] = f"http://{announce_host}/announce"
            return bencode.bencode(torrent_dict)
        except Exception as e:
            print(f"[!] Error adjusting torrent announce: {e}")
            return raw


def make_request_handler(server_instance: SpeedtestServer):
    class SpeedtestHTTPHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Suppress normal tracker polling spam from terminal
            if "/api/stats" in str(args[0]) or "/announce" in str(args[0]):
                return
            super().log_message(format, *args)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query_str = parsed.query

            client_ip = self.client_address[0]
            host_hdr = self.headers.get("Host", f"localhost:{server_instance.http_port}")

            # 1. Main Web UI
            if path == "/" or path == "/index.html":
                content = HTML_TEMPLATE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

            # 2. Download .torrent file
            elif path in ("/speedtest-5gb.torrent", "/speedtest.torrent"):
                torrent_bytes = server_instance.get_dynamic_torrent_bytes(host_hdr)
                if not torrent_bytes:
                    self.send_error(404, "Torrent file not generated yet")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/x-bittorrent")
                self.send_header("Content-Disposition", 'attachment; filename="speedtest-5gb.torrent"')
                self.send_header("Content-Length", str(len(torrent_bytes)))
                self.end_headers()
                self.wfile.write(torrent_bytes)
                return

            # 3. BitTorrent HTTP Tracker Announce
            elif path == "/announce":
                params = parse_tracker_query(query_str)
                resp_bytes = server_instance.tracker.handle_announce(params, client_ip)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)
                return

            # 4. BitTorrent Scrape
            elif path == "/scrape":
                params = parse_tracker_query(query_str)
                resp_bytes = server_instance.tracker.handle_scrape(params)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)
                return

            # 5. Live Stats API
            elif path == "/api/stats":
                trans_stats = server_instance.transmission.get_session_stats()
                tracker_stats = server_instance.tracker.get_stats()
                meta = dict(server_instance.metadata)

                announce_url = f"http://{server_instance.public_host}:{server_instance.http_port}/announce"
                if meta.get("info_hash_hex"):
                    meta["magnet_uri"] = f"magnet:?xt=urn:btih:{meta['info_hash_hex']}&dn={meta.get('file_name', 'speedtest-5gb.bin')}&tr={urllib.parse.quote(announce_url)}"

                data = {
                    "network": {
                        "public_host": server_instance.public_host,
                        "seeder_ip": server_instance.seeder_ip,
                        "seeder_port": server_instance.seeder_port,
                        "http_port": server_instance.http_port,
                        "announce_url": announce_url,
                    },
                    "transmission": trans_stats,
                    "tracker": tracker_stats,
                    "metadata": meta,
                }
                resp_body = json.dumps(data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp_body)
                return

            # 6. Health check
            elif path == "/health":
                body = b"OK"
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            else:
                self.send_error(404, "Not Found")

    return SpeedtestHTTPHandler


def run_server():
    data_dir = os.environ.get("DATA_DIR", "/data")
    http_host = os.environ.get("HTTP_HOST", "0.0.0.0")
    http_port = int(os.environ.get("HTTP_PORT", "8080"))
    public_host = os.environ.get("PUBLIC_HOST")
    seeder_port = int(os.environ.get("PEER_PORT", "51413"))
    transmission_rpc = os.environ.get("TRANSMISSION_RPC_URL", "http://127.0.0.1:9091/transmission/rpc")

    server_instance = SpeedtestServer(
        data_dir=data_dir,
        http_host=http_host,
        http_port=http_port,
        public_host=public_host,
        seeder_port=seeder_port,
        transmission_rpc_url=transmission_rpc,
    )

    handler_class = make_request_handler(server_instance)
    httpd = http.server.ThreadingHTTPServer((http_host, http_port), handler_class)

    print(f"[+] Speed Test Web UI & Tracker running on http://{http_host}:{http_port}")
    print(f"[+] Seeder Wire Port: {seeder_port}")
    print(f"[+] Public Announce: http://{server_instance.public_host}:{http_port}/announce")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down HTTP server...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
