"""A short code that guards the first administrator account on a server open to the internet.

Whoever creates the first account owns the server. On a home network that is fine, because only
people at home can reach it. On a public address, anyone could get there first. So when the
request does not come from the local network, the person must type a code that only someone with
access to the server's files or logs can read.
"""

import ipaddress
import secrets
from pathlib import Path

FILE = "setup-code.txt"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0, O, 1, I or L to mix up
LENGTH = 10


def is_local_address(host: str) -> bool:
    """True for this computer and the private network. A name that is not an address counts as
    local too, since a real connection always arrives from an address."""
    try:
        address = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return True
    return address.is_private or address.is_loopback or address.is_link_local


def get_or_create(data_dir: Path) -> str:
    file = data_dir / FILE
    try:
        existing = file.read_text(encoding="utf-8").strip()
    except OSError:
        existing = ""
    if existing:
        return existing
    code = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
    data_dir.mkdir(parents=True, exist_ok=True)
    file.write_text(code + "\n", encoding="utf-8")
    return code


def matches(data_dir: Path, given: str) -> bool:
    expected = get_or_create(data_dir)
    return secrets.compare_digest(expected.encode(), given.strip().upper().encode())


def clear(data_dir: Path) -> None:
    (data_dir / FILE).unlink(missing_ok=True)
