"""
Helper to communicate with Transmission Daemon via its JSON-RPC.
Uses Python standard library only.
"""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class TransmissionClient:
    """Minimal JSON-RPC client for the Transmission daemon."""

    def __init__(self, rpc_url: str = "http://127.0.0.1:9091/transmission/rpc"):
        self.rpc_url = rpc_url
        self.session_id: str | None = None

    def request(
        self,
        method: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call an RPC method, handling the 409 session-id handshake."""
        payload = {"method": method, "arguments": arguments or {}}
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(self.rpc_url, data=data, headers=headers)
        if self.session_id:
            req.add_header("X-Transmission-Session-Id", self.session_id)

        if urllib.parse.urlparse(self.rpc_url).scheme not in ("http", "https"):
            raise ValueError(f"Unsupported RPC URL scheme: {self.rpc_url}")

        try:
            # nosec B310 - scheme validated above
            with urllib.request.urlopen(req, timeout=3) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 409:
                self.session_id = e.headers.get("X-Transmission-Session-Id")
                if self.session_id:
                    # Retry with new session id
                    req = urllib.request.Request(
                        self.rpc_url,
                        data=data,
                        headers={
                            "Content-Type": "application/json",
                            "X-Transmission-Session-Id": self.session_id,
                        },
                    )
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        return json.loads(resp.read().decode("utf-8"))
            raise

    def get_session_stats(self) -> dict[str, Any]:
        """Return session statistics, or an error entry if unavailable."""
        try:
            res = self.request("session-stats")
            return res.get("arguments", {})
        except (OSError, ValueError) as e:
            return {"error": str(e)}

    def get_torrents(self) -> list:
        """Return the torrent list, or an empty list if unavailable."""
        try:
            res = self.request(
                "torrent-get",
                {
                    "fields": [
                        "id",
                        "name",
                        "rateUpload",
                        "peersSendingToUs",
                        "peersGettingFromUs",
                        "percentDone",
                        "status",
                    ]
                },
            )
            return res.get("arguments", {}).get("torrents", [])
        except (OSError, ValueError):
            return []

    def add_torrent(self, torrent_path: str, download_dir: str) -> dict[str, Any]:
        """Add a torrent file by path."""
        with open(torrent_path, "rb") as f:
            metainfo = base64.b64encode(f.read()).decode("ascii")
        res = self.request(
            "torrent-add",
            {
                "metainfo": metainfo,
                "download-dir": download_dir,
                "paused": False,
            },
        )
        return res

    def start_all(self) -> dict[str, Any]:
        """Start all torrents."""
        return self.request("torrent-start")

    def verify_all(self) -> dict[str, Any]:
        """Verify all torrents."""
        return self.request("torrent-verify")
