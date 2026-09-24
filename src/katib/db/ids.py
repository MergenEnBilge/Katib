"""UUIDv7 generation. Ids sort by creation time, which keeps index inserts append-mostly."""

import os
import time
import uuid


def new_id() -> uuid.UUID:
    ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms & 0xFFFFFFFFFFFF) << 80
    value |= 0x7 << 76
    value |= ((rand >> 68) & 0xFFF) << 64
    value |= 0b10 << 62
    value |= rand & 0x3FFFFFFFFFFFFFFF
    return uuid.UUID(int=value)
