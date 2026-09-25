"""Finding the addresses other devices can use to reach this computer, and QR codes for them."""

import io
import socket

import segno


def lan_addresses() -> list[str]:
    """IPv4 addresses of this computer on the local network, most likely one first."""
    found: list[str] = []
    # Connecting a UDP socket sends nothing. It only makes the system pick the outgoing interface.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 9))
            found.append(str(probe.getsockname()[0]))
        except OSError:
            pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = str(info[4][0])
            if address not in found:
                found.append(address)
    except OSError:
        pass
    return [a for a in found if not a.startswith(("127.", "169.254."))]


def qr_svg(text: str) -> str:
    """A QR code for `text` as an SVG document."""
    buffer = io.BytesIO()
    segno.make(text, error="m").save(buffer, kind="svg", scale=8, border=2, dark="#111111")
    return buffer.getvalue().decode("utf-8")


def qr_terminal(text: str) -> str:
    """A QR code for `text` drawn with block characters, for printing in a terminal."""
    buffer = io.StringIO()
    segno.make(text, error="l").terminal(out=buffer, compact=True, border=2)
    return buffer.getvalue()
