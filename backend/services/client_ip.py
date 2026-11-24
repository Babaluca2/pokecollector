"""Real client address for rate limiting.

The backend normally sits behind the bundled nginx, so the socket peer is the
nginx container. nginx resolves the visitor's address (through the tunnel or
reverse proxy in front of it) and passes it as ``X-Real-IP``. That header is
only trusted when the direct peer is a private or loopback address, so a
client reaching the backend from the internet cannot forge it.
"""

from __future__ import annotations

import ipaddress

from starlette.requests import Request


def _is_private(value: str | None) -> bool:
    try:
        address = ipaddress.ip_address(value or "")
    except ValueError:
        return False
    return address.is_private or address.is_loopback


def _valid_ip(value: str | None) -> str | None:
    try:
        return str(ipaddress.ip_address((value or "").strip()))
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else None
    if _is_private(peer):
        forwarded = _valid_ip(request.headers.get("x-real-ip"))
        if forwarded:
            return forwarded
    return peer or "unknown"
