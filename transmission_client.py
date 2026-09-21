"""
Helper to communicate with Transmission Daemon via its JSON-RPC.
Uses Python standard library only.
"""
import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class TransmissionClient:
    def __init__(self, rpc_url: str = "http://127.0.0.1:9091/transmission/rpc"):
        self.rpc_url = rpc_url
        self.session_id: Optional[str] = None

    def request(self, method: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = json.dumps({"method": method, "arguments": arguments or {}}).encode("utf-8")
        req = urllib.request.Request(self.rpc_url, data=data, headers={"Content-Type": "application/json"})
        if self.session_id:
            req.add_header("X-Transmission-Session-Id", self.session_id)

        try:
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

    def get_session_stats(self) -> Dict[str, Any]:
        try:
            res = self.request("session-stats")
            return res.get("arguments", {})
        except Exception as e:
            return {"error": str(e)}

    def get_torrents(self) -> list:
        try:
            res = self.request("torrent-get", {"fields": ["id", "name", "rateUpload", "peersSendingToUs", "peersGettingFromUs", "percentDone", "status"]})
            return res.get("arguments", {}).get("torrents", [])
        except Exception:
            return []

    def add_torrent(self, torrent_path: str, download_dir: str) -> Dict[str, Any]:
        """Add a torrent file by path."""
        import base64
        with open(torrent_path, "rb") as f:
            metainfo = base64.b64encode(f.read()).decode("ascii")
        res = self.request("torrent-add", {
            "metainfo": metainfo,
            "download-dir": download_dir,
            "paused": False,
        })
        return res

    def start_all(self) -> Dict[str, Any]:
        """Start all torrents."""
        return self.request("torrent-start")

    def verify_all(self) -> Dict[str, Any]:
        """Verify all torrents."""
        return self.request("torrent-verify")

