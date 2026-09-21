"""
Lightweight, pure-Python Bencode encoder and decoder.
Follows the BitTorrent BEP 0003 specification.
"""
from typing import Any, Tuple, Union


def bencode(val: Any) -> bytes:
    """Encode Python objects (int, bytes, str, list, dict) into bencoded bytes."""
    if isinstance(val, int):
        return f"i{val}e".encode("ascii")
    elif isinstance(val, bytes):
        return f"{len(val)}:".encode("ascii") + val
    elif isinstance(val, str):
        b = val.encode("utf-8")
        return f"{len(b)}:".encode("ascii") + b
    elif isinstance(val, list) or isinstance(val, tuple):
        items = b"".join(bencode(item) for item in val)
        return b"l" + items + b"e"
    elif isinstance(val, dict):
        # Keys in bencoded dictionaries must be strings/bytes and sorted lexicographically
        encoded_dict = bytearray(b"d")
        # Normalize keys to bytes for proper sorting
        items = []
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
    else:
        raise TypeError(f"Cannot bencode object of type {type(val)}")


def bdecode(data: bytes) -> Any:
    """Decode bencoded bytes into Python objects."""
    res, index = _bdecode_item(data, 0)
    return res


def _bdecode_item(data: bytes, index: int) -> Tuple[Any, int]:
    if index >= len(data):
        raise ValueError("Unexpected end of bencoded data")

    char = data[index : index + 1]

    if char == b"i":
        end = data.index(b"e", index)
        num = int(data[index + 1 : end])
        return num, end + 1

    elif char == b"l":
        res = []
        index += 1
        while data[index : index + 1] != b"e":
            item, index = _bdecode_item(data, index)
            res.append(item)
        return res, index + 1

    elif char == b"d":
        res = {}
        index += 1
        while data[index : index + 1] != b"e":
            key_bytes, index = _bdecode_item(data, index)
            if not isinstance(key_bytes, bytes):
                raise ValueError(f"Dictionary key must be string/bytes, got {type(key_bytes)}")
            # Keep key as str if valid utf-8, else bytes
            try:
                key = key_bytes.decode("utf-8")
            except UnicodeDecodeError:
                key = key_bytes
            val, index = _bdecode_item(data, index)
            res[key] = val
        return res, index + 1

    elif char.isdigit():
        colon = data.index(b":", index)
        length = int(data[index:colon])
        start = colon + 1
        end = start + length
        return data[start:end], end

    else:
        raise ValueError(f"Invalid bencode token at index {index}: {char}")
