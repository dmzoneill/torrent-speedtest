"""
Generates dummy test data and the corresponding BitTorrent .torrent file.
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any

import bencode

MB = 1024 * 1024
WRITE_CHUNK = 16 * MB
PROGRESS_STEP = 512 * MB


@dataclass
class SpeedtestSpec:
    """Parameters describing the dummy payload and its torrent."""

    data_dir: str = "/data"
    file_name: str = "speedtest-5gb.bin"
    size_gb: float = 5.0
    piece_size_mb: int = 4
    public_host: str = "localhost"
    http_port: int = 8080

    @property
    def total_bytes(self) -> int:
        """Payload size in bytes."""
        return int(self.size_gb * 1024 * MB)

    @property
    def piece_length(self) -> int:
        """Torrent piece length in bytes."""
        return self.piece_size_mb * MB

    @property
    def announce_url(self) -> str:
        """Tracker announce URL embedded in the torrent."""
        return f"http://{self.public_host}:{self.http_port}/announce"


class _PieceHasher:
    """Accumulates SHA1 piece hashes over a stream of bytes."""

    def __init__(self, piece_length: int):
        self.piece_length = piece_length
        self.pieces = bytearray()
        self._hasher = hashlib.sha1(usedforsecurity=False)
        self._filled = 0

    def update(self, data: memoryview) -> None:
        """Feed bytes, closing pieces as they fill up."""
        offset = 0
        while offset < len(data):
            take = min(self.piece_length - self._filled, len(data) - offset)
            self._hasher.update(data[offset : offset + take])
            self._filled += take
            offset += take
            if self._filled == self.piece_length:
                self._close_piece()

    def finish(self) -> bytes:
        """Close any partial last piece and return all piece hashes."""
        if self._filled > 0:
            self._close_piece()
        return bytes(self.pieces)

    def _close_piece(self) -> None:
        self.pieces.extend(self._hasher.digest())
        self._hasher = hashlib.sha1(usedforsecurity=False)
        self._filled = 0


def _report_progress(bytes_written: int, total_bytes: int, start_time: float) -> None:
    """Print write progress and throughput."""
    progress = (bytes_written / total_bytes) * 100
    elapsed = time.time() - start_time
    speed = (bytes_written / MB) / (elapsed if elapsed > 0 else 0.001)
    line = f"    -> {progress:5.1f}% written ({bytes_written // MB} MB)"
    print(f"{line} at {speed:.1f} MB/s", flush=True)


def _write_payload(file_path: str, total_bytes: int, piece_length: int) -> bytes:
    """Write the pseudo-random payload and return its concatenated piece hashes."""
    start_time = time.time()
    # Pre-generate 16MB of random bytes, written in cycles: fast and incompressible
    pattern = bytearray(os.urandom(WRITE_CHUNK))
    hasher = _PieceHasher(piece_length)
    bytes_written = 0

    with open(file_path, "wb") as f:
        while bytes_written < total_bytes:
            to_write = min(WRITE_CHUNK, total_bytes - bytes_written)
            # Slightly mutate pattern to prevent basic compression
            pattern[0] = (pattern[0] + 1) & 0xFF
            pattern[1] = (pattern[1] + 7) & 0xFF
            data_slice = memoryview(pattern)[:to_write]
            f.write(data_slice)
            hasher.update(data_slice)

            bytes_written += to_write
            if bytes_written % PROGRESS_STEP == 0 or bytes_written == total_bytes:
                _report_progress(bytes_written, total_bytes, start_time)

    elapsed = time.time() - start_time
    avg_speed = (total_bytes / MB) / elapsed
    print(f"[+] 5GB dummy file created in {elapsed:.2f}s (Avg {avg_speed:.1f} MB/s)")
    return hasher.finish()


def _write_torrent(spec: SpeedtestSpec, torrent_path: str, pieces: bytes) -> str:
    """Write the .torrent file and return its hex info hash."""
    info_dict = {
        "length": spec.total_bytes,
        "name": spec.file_name,
        "piece length": spec.piece_length,
        "pieces": pieces,
        # Private flag disables DHT/PEX so clients only use our speedtest tracker
        "private": 1,
    }
    bencoded_info = bencode.bencode(info_dict)
    # SHA-1 info hash is mandated by BitTorrent v1 (BEP 3), not security.
    info_hash_hex = hashlib.sha1(  # nosemgrep
        bencoded_info, usedforsecurity=False
    ).hexdigest()

    torrent_dict = {
        "announce": spec.announce_url,
        "comment": "Torrent Speedtest - 5GB Dummy File",
        "created by": "Torrent-Speedtest Generator",
        "creation date": int(time.time()),
        "info": info_dict,
    }
    with open(torrent_path, "wb") as f:
        f.write(bencode.bencode(torrent_dict))
    return info_hash_hex


def generate_test_file_and_torrent(
    spec: SpeedtestSpec,
    force: bool = False,
) -> dict[str, Any]:
    """
    Creates the dummy binary file (if not existing) and the .torrent metadata.
    """
    os.makedirs(spec.data_dir, exist_ok=True)
    file_path = os.path.join(spec.data_dir, spec.file_name)
    torrent_name = f"{os.path.splitext(spec.file_name)[0]}.torrent"
    torrent_path = os.path.join(spec.data_dir, torrent_name)
    meta_json_path = os.path.join(spec.data_dir, "speedtest-info.json")
    total_bytes = spec.total_bytes

    file_ok = os.path.exists(file_path) and os.path.getsize(file_path) == total_bytes
    torrent_ok = os.path.exists(torrent_path) and os.path.exists(meta_json_path)

    if file_ok and torrent_ok and not force:
        print(f"[*] Found existing data and torrent in {spec.data_dir}.")
        print("[*] Loading metadata...")
        with open(meta_json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"[*] Generating {spec.size_gb:.1f} GB test file at {file_path}...")
    pieces = _write_payload(file_path, total_bytes, spec.piece_length)
    info_hash_hex = _write_torrent(spec, torrent_path, pieces)

    magnet_uri = f"magnet:?xt=urn:btih:{info_hash_hex}&dn={spec.file_name}"
    magnet_uri += f"&tr={spec.announce_url}"
    metadata = {
        "file_name": spec.file_name,
        "file_size": total_bytes,
        "size_gb": spec.size_gb,
        "piece_size": spec.piece_length,
        "piece_count": len(pieces) // 20,
        "info_hash_hex": info_hash_hex,
        "announce_url": spec.announce_url,
        "magnet_uri": magnet_uri,
        "torrent_file": torrent_path,
        "data_file": file_path,
    }

    with open(meta_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("[+] Torrent created successfully!")
    print(f"    Info Hash: {info_hash_hex}")
    print(f"    Torrent:   {torrent_path}")
    print(f"    Pieces:    {len(pieces) // 20} x {spec.piece_size_mb}MB")
    return metadata


def main() -> None:
    """Generate the payload and torrent using settings from the environment."""
    generate_test_file_and_torrent(
        SpeedtestSpec(
            data_dir=os.environ.get("DATA_DIR", "./data"),
            file_name=os.environ.get("FILE_NAME", "speedtest-5gb.bin"),
            size_gb=float(os.environ.get("FILE_SIZE_GB", "5.0")),
            piece_size_mb=int(os.environ.get("PIECE_SIZE_MB", "4")),
            public_host=os.environ.get("PUBLIC_HOST", "localhost"),
            http_port=int(os.environ.get("HTTP_PORT", "8080")),
        )
    )


if __name__ == "__main__":
    main()
