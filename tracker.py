"""
BitTorrent HTTP Tracker Implementation (BEP 0003, BEP 0023, BEP 0048).
"""
import socket
import struct
import time
from typing import Any, Dict, List, Optional, Tuple

import bencode


class Tracker:
    def __init__(self, seeder_ip: str = "127.0.0.1", seeder_port: int = 51413, interval: int = 30):
        self.seeder_ip = seeder_ip
        self.seeder_port = seeder_port
        self.interval = interval
        self.min_interval = 15
        # info_hash_hex -> { peer_id_hex: { "ip": str, "port": int, "left": int, "peer_id_raw": bytes, "last_seen": float } }
        self.torrents: Dict[str, Dict[str, Dict[str, Any]]] = {}
        # Count of completions
        self.completed_counts: Dict[str, int] = {}

    def update_seeder(self, ip: Optional[str] = None, port: Optional[int] = None):
        if ip:
            self.seeder_ip = ip
        if port:
            self.seeder_port = port

    def prune_stale_peers(self, timeout: float = 180.0):
        """Remove peers that haven't announced within `timeout` seconds."""
        now = time.time()
        for info_hash, peers in list(self.torrents.items()):
            stale_keys = [pid for pid, data in peers.items() if now - data["last_seen"] > timeout]
            for pid in stale_keys:
                del peers[pid]

    def handle_announce(
        self,
        params: Dict[str, bytes],
        client_ip: str,
    ) -> bytes:
        """Process an announce request and return bencoded response."""
        self.prune_stale_peers()

        info_hash_bytes = params.get("info_hash")
        if not info_hash_bytes or len(info_hash_bytes) != 20:
            return bencode.bencode({"failure reason": "Invalid info_hash (must be 20 bytes)"})

        info_hash_hex = info_hash_bytes.hex()
        peer_id_bytes = params.get("peer_id", b"")
        peer_id_hex = peer_id_bytes.hex()

        try:
            port = int(params.get("port", b"0").decode("ascii"))
        except ValueError:
            return bencode.bencode({"failure reason": "Invalid port number"})

        try:
            left = int(params.get("left", b"0").decode("ascii"))
        except ValueError:
            left = 0

        event = params.get("event", b"").decode("ascii", errors="ignore").lower()
        compact = params.get("compact", b"0").decode("ascii", errors="ignore") == "1"

        try:
            numwant = int(params.get("numwant", b"50").decode("ascii"))
            numwant = max(1, min(numwant, 200))
        except ValueError:
            numwant = 50

        if info_hash_hex not in self.torrents:
            self.torrents[info_hash_hex] = {}
            self.completed_counts[info_hash_hex] = 0

        peers_dict = self.torrents[info_hash_hex]

        # Handle events
        if event == "stopped":
            if peer_id_hex in peers_dict:
                del peers_dict[peer_id_hex]
            return bencode.bencode({
                "interval": self.interval,
                "min interval": self.min_interval,
                "complete": 1 + sum(1 for p in peers_dict.values() if p["left"] == 0),
                "incomplete": sum(1 for p in peers_dict.values() if p["left"] > 0),
                "peers": b"" if compact else [],
            })

        if event == "completed":
            self.completed_counts[info_hash_hex] = self.completed_counts.get(info_hash_hex, 0) + 1

        # Record or update peer
        peers_dict[peer_id_hex] = {
            "ip": client_ip,
            "port": port,
            "left": left,
            "peer_id_raw": peer_id_bytes,
            "last_seen": time.time(),
        }

        # Build list of peers to return
        # Always prioritize returning the local seeder so the client connects to our speed test payload!
        candidate_peers: List[Tuple[str, int, bytes]] = []

        # 1. Add container seeder
        if self.seeder_ip and self.seeder_port:
            candidate_peers.append((self.seeder_ip, self.seeder_port, b"-ST0001-SEEDERPEER01"))

        # 2. Add other active peers (excluding the requesting peer)
        for pid, pdata in peers_dict.items():
            if pid != peer_id_hex:
                candidate_peers.append((pdata["ip"], pdata["port"], pdata["peer_id_raw"]))
            if len(candidate_peers) >= numwant:
                break

        # Calculate complete / incomplete counts
        seeders_count = 1 + sum(1 for p in peers_dict.values() if p["left"] == 0)
        leechers_count = sum(1 for p in peers_dict.values() if p["left"] > 0)

        response: Dict[str, Any] = {
            "interval": self.interval,
            "min interval": self.min_interval,
            "complete": seeders_count,
            "incomplete": leechers_count,
        }

        if compact:
            # 6 bytes per peer: 4 bytes IPv4 + 2 bytes port (big-endian)
            compact_peers = bytearray()
            for ip_str, p_port, _ in candidate_peers:
                try:
                    # Attempt IPv4 conversion
                    ip_packed = socket.inet_aton(ip_str)
                    port_packed = struct.pack(">H", p_port)
                    compact_peers.extend(ip_packed + port_packed)
                except (socket.error, struct.error):
                    continue
            response["peers"] = bytes(compact_peers)
        else:
            # Dictionary format
            peer_list = []
            for ip_str, p_port, p_raw in candidate_peers:
                peer_list.append({
                    "peer id": p_raw,
                    "ip": ip_str,
                    "port": p_port,
                })
            response["peers"] = peer_list

        return bencode.bencode(response)

    def handle_scrape(self, params: Dict[str, bytes]) -> bytes:
        """Handle BEP 0048 scrape request."""
        self.prune_stale_peers()
        files = {}
        # If info_hash specified, scrape only that one; otherwise scrape all
        req_hash = params.get("info_hash")
        hashes_to_scrape = [req_hash.hex()] if req_hash else list(self.torrents.keys())

        for ih_hex in hashes_to_scrape:
            peers_dict = self.torrents.get(ih_hex, {})
            seeders = 1 + sum(1 for p in peers_dict.values() if p["left"] == 0)
            leechers = sum(1 for p in peers_dict.values() if p["left"] > 0)
            downloaded = self.completed_counts.get(ih_hex, 0)
            try:
                raw_hash = bytes.fromhex(ih_hex)
                files[raw_hash] = {
                    "complete": seeders,
                    "downloaded": downloaded,
                    "incomplete": leechers,
                }
            except ValueError:
                pass

        return bencode.bencode({"files": files})

    def get_stats(self) -> Dict[str, Any]:
        """Return general tracker statistics."""
        self.prune_stale_peers()
        total_peers = sum(len(p) for p in self.torrents.values())
        active_leechers = sum(sum(1 for p in t.values() if p["left"] > 0) for t in self.torrents.values())
        return {
            "seeder_ip": self.seeder_ip,
            "seeder_port": self.seeder_port,
            "tracked_torrents": len(self.torrents),
            "active_peers": total_peers,
            "active_leechers": active_leechers,
        }
