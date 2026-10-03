"""A short code that guards the first administrator account on a server other people can reach.

Whoever creates the first account owns the server. While Katib answers only on the computer it
runs on, nobody else can get there, so there is nothing to guard. The moment it is opened to a
network, anyone who can reach it could claim that account first — the wifi in an office or a cafe
is not a list of people you trust, and Katib cannot tell a colleague from a stranger by address.

So a server open to a network asks for a code that only someone who can read its files or its log
can know. It is printed when Katib starts and kept in setup-code.txt, and it stops working as soon
as the first account exists.
"""

import contextlib
import ipaddress
import secrets
from collections.abc import Mapping
from pathlib import Path

FILE = "setup-code.txt"
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0, O, 1, I or L to mix up
LENGTH = 10


def is_local_address(host: str) -> bool:
    """True for this computer and the private network. A name that is not an address counts as
    local too, since a real connection always arrives from an address."""
    try:
        address = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return True
    return address.is_private or address.is_loopback or address.is_link_local


PROXY_HEADERS = ("x-forwarded-for", "x-real-ip", "forwarded")


def needs_code(
    address: str, headers: Mapping[str, str], trusts_proxy: bool, *, on_a_network: bool
) -> bool:
    """Whether creating the first account from here calls for the setup code.

    Everyone does once Katib is listening on a network address, including whoever is sitting at
    the server: telling them apart from the next person on the same wifi is not something an
    address can do.

    On a server closed to everything but itself, the code is only asked for when the request
    cannot have come from that computer: an address that is not private, or a proxy Katib was not
    told to trust, whose address says nothing about who is really behind it.
    """
    if on_a_network or not is_local_address(address):
        return True
    return not trusts_proxy and any(name in headers for name in PROXY_HEADERS)


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
    with contextlib.suppress(OSError):
        file.chmod(0o600)
    return code


def pending(data_dir: Path) -> str | None:
    """The code, while a server for this data folder is waiting for its first administrator.

    For programs on the server's own computer to fill it in for whoever sits there: reading this
    file is what proves they may, since only the account that runs Katib can.
    """
    try:
        return (data_dir / FILE).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def setup_link(url: str, code: str | None) -> str:
    """The address of the server's start page, carrying the code after the `#`. Browsers keep
    that part to themselves: it never reaches a server, a proxy or a log."""
    return f"{url}/#setup-code={code}" if code else url


def matches(data_dir: Path, given: str) -> bool:
    expected = get_or_create(data_dir)
    return secrets.compare_digest(expected.encode(), given.strip().upper().encode())


def clear(data_dir: Path) -> None:
    (data_dir / FILE).unlink(missing_ok=True)
