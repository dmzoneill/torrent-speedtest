"""
Lightweight, pure-Python Bencode encoder and decoder.
Follows the BitTorrent BEP 0003 specification.
"""

from typing import Any


def bencode(val: Any) -> bytes:
    """Encode Python objects (int, bytes, str, list, dict) into bencoded bytes."""
    if isinstance(val, int):
        return f"i{val}e".encode("ascii")
    if isinstance(val, bytes):
        return f"{len(val)}:".encode("ascii") + val
    if isinstance(val, str):
        b = val.encode("utf-8")
        return f"{len(b)}:".encode("ascii") + b
    if isinstance(val, (list, tuple)):
        encoded_items = b"".join(bencode(item) for item in val)
        return b"l" + encoded_items + b"e"
    if isinstance(val, dict):
        # Bencoded dictionary keys must be strings/bytes, sorted lexicographically
        encoded_dict = bytearray(b"d")
        # Normalize keys to bytes for proper sorting
        items: list[tuple[bytes, Any]] = []
        for k, v in val.items():
            if isinstance(k, str):
                items.append((k.encode("utf-8"), v))
            elif isinstance(k, bytes):
                items.append((k, v))
            else:
                raise TypeError(f"Dict key must be str or bytes, got {type(k)}")
        items.sort(key=lambda x: x[0])
        for k_bytes, v in items:
            encoded_dict.extend(f"{len(k_bytes)}:".encode("ascii") + k_bytes)
            encoded_dict.extend(bencode(v))
        encoded_dict.extend(b"e")
        return bytes(encoded_dict)
    raise TypeError(f"Cannot bencode object of type {type(val)}")


def bdecode(data: bytes) -> Any:
    """Decode bencoded bytes into Python objects."""
    res, _ = _bdecode_item(data, 0)
    return res


def _bdecode_item(data: bytes, index: int) -> tuple[Any, int]:
    if index >= len(data):
        raise ValueError("Unexpected end of bencoded data")

    char = data[index : index + 1]

    if char == b"i":
        end = data.index(b"e", index)
        num = int(data[index + 1 : end])
        return num, end + 1

    if char == b"l":
        res_list: list[Any] = []
        index += 1
        while data[index : index + 1] != b"e":
            item, index = _bdecode_item(data, index)
            res_list.append(item)
        return res_list, index + 1

    if char == b"d":
        res_dict: dict[str | bytes, Any] = {}
        index += 1
        while data[index : index + 1] != b"e":
            key_bytes, index = _bdecode_item(data, index)
            if not isinstance(key_bytes, bytes):
                msg = f"Dictionary key must be string/bytes, got {type(key_bytes)}"
                raise TypeError(msg)
            # Keep key as str if valid utf-8, else bytes
            key: str | bytes
            try:
                key = key_bytes.decode("utf-8")
            except UnicodeDecodeError:
                key = key_bytes
            val, index = _bdecode_item(data, index)
            res_dict[key] = val
        return res_dict, index + 1

    if char.isdigit():
        colon = data.index(b":", index)
        length = int(data[index:colon])
        start = colon + 1
        end = start + length
        return data[start:end], end

    raise ValueError(f"Invalid bencode token at index {index}: {char!r}")
