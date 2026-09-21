"""
Generates dummy test data and the corresponding BitTorrent .torrent file.
"""
import hashlib
import json
import os
import sys
import time
from typing import Dict, Any

import bencode


def generate_test_file_and_torrent(
    data_dir: str = "/data",
    file_name: str = "speedtest-5gb.bin",
    size_gb: float = 5.0,
    piece_size_mb: int = 4,
    public_host: str = "localhost",
    http_port: int = 8080,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Creates the dummy binary file (if not existing) and the .torrent metadata.
    """
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, file_name)
    torrent_path = os.path.join(data_dir, f"{os.path.splitext(file_name)[0]}.torrent")
    meta_json_path = os.path.join(data_dir, "speedtest-info.json")

    total_bytes = int(size_gb * 1024 * 1024 * 1024)
    piece_length = piece_size_mb * 1024 * 1024

    file_exists = os.path.exists(file_path) and os.path.getsize(file_path) == total_bytes
    torrent_exists = os.path.exists(torrent_path) and os.path.exists(meta_json_path)

    if file_exists and torrent_exists and not force:
        print(f"[*] Found existing data and torrent in {data_dir}. Loading metadata...")
        with open(meta_json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"[*] Generating {size_gb:.1f} GB ({total_bytes} bytes) test file at {file_path}...")
    start_time = time.time()

    # Pre-generate 16MB of pseudo-random bytes to write in cycles for high speed and non-compressibility
    chunk_size = 16 * 1024 * 1024
    pattern = bytearray(os.urandom(chunk_size))

    pieces_hashes = bytearray()
    bytes_written = 0
    current_piece_hasher = hashlib.sha1()
    current_piece_bytes = 0

    with open(file_path, "wb") as f:
        while bytes_written < total_bytes:
            to_write = min(chunk_size, total_bytes - bytes_written)
            # Slightly mutate pattern to prevent basic compression
            pattern[0] = (pattern[0] + 1) & 0xFF
            pattern[1] = (pattern[1] + 7) & 0xFF
            data_slice = memoryview(pattern)[:to_write]
            f.write(data_slice)

            # Hash the pieces
            offset = 0
            while offset < to_write:
                needed = piece_length - current_piece_bytes
                avail = to_write - offset
                take = min(needed, avail)
                current_piece_hasher.update(data_slice[offset : offset + take])
                current_piece_bytes += take
                offset += take

                if current_piece_bytes == piece_length:
                    pieces_hashes.extend(current_piece_hasher.digest())
                    current_piece_hasher = hashlib.sha1()
                    current_piece_bytes = 0

            bytes_written += to_write
            if bytes_written % (512 * 1024 * 1024) == 0 or bytes_written == total_bytes:
                progress = (bytes_written / total_bytes) * 100
                elapsed = time.time() - start_time
                speed = (bytes_written / (1024 * 1024)) / (elapsed if elapsed > 0 else 0.001)
                print(f"    -> {progress:5.1f}% written ({bytes_written // (1024*1024)} MB) at {speed:.1f} MB/s", flush=True)

    # If the last piece was partial
    if current_piece_bytes > 0:
        pieces_hashes.extend(current_piece_hasher.digest())

    elapsed = time.time() - start_time
    print(f"[+] 5GB dummy file created in {elapsed:.2f}s (Avg {(total_bytes / (1024*1024)) / elapsed:.1f} MB/s)")

    announce_url = f"http://{public_host}:{http_port}/announce"

    info_dict = {
        "length": total_bytes,
        "name": file_name,
        "piece length": piece_length,
        "pieces": bytes(pieces_hashes),
        "private": 1,  # Private flag disables DHT/PEX so client only connects to our speedtest tracker
    }

    # Compute info_hash
    bencoded_info = bencode.bencode(info_dict)
    info_hash_bytes = hashlib.sha1(bencoded_info).digest()
    info_hash_hex = hashlib.sha1(bencoded_info).hexdigest()

    torrent_dict = {
        "announce": announce_url,
        "comment": "Torrent Speedtest - 5GB Dummy File",
        "created by": "Torrent-Speedtest Generator",
        "creation date": int(time.time()),
        "info": info_dict,
    }

    bencoded_torrent = bencode.bencode(torrent_dict)
    with open(torrent_path, "wb") as f:
        f.write(bencoded_torrent)

    magnet_uri = f"magnet:?xt=urn:btih:{info_hash_hex}&dn={file_name}&tr={announce_url}"

    metadata = {
        "file_name": file_name,
        "file_size": total_bytes,
        "size_gb": size_gb,
        "piece_size": piece_length,
        "piece_count": len(pieces_hashes) // 20,
        "info_hash_hex": info_hash_hex,
        "announce_url": announce_url,
        "magnet_uri": magnet_uri,
        "torrent_file": torrent_path,
        "data_file": file_path,
    }

    with open(meta_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[+] Torrent created successfully!")
    print(f"    Info Hash: {info_hash_hex}")
    print(f"    Torrent:   {torrent_path}")
    print(f"    Pieces:    {len(pieces_hashes) // 20} x {piece_size_mb}MB")
    return metadata


if __name__ == "__main__":
    data_dir = os.environ.get("DATA_DIR", "./data")
    file_name = os.environ.get("FILE_NAME", "speedtest-5gb.bin")
    size_gb = float(os.environ.get("FILE_SIZE_GB", "5.0"))
    piece_size_mb = int(os.environ.get("PIECE_SIZE_MB", "4"))
    public_host = os.environ.get("PUBLIC_HOST", "localhost")
    http_port = int(os.environ.get("HTTP_PORT", "8080"))

    generate_test_file_and_torrent(
        data_dir=data_dir,
        file_name=file_name,
        size_gb=size_gb,
        piece_size_mb=piece_size_mb,
        public_host=public_host,
        http_port=http_port,
    )
