"""Conservative validation for explicitly trusted direct-media hosts."""
from __future__ import annotations
import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit
from .models import UnsafeSource

async def check_source(url: str, allowed_hosts: tuple[str, ...], allow_private: bool) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeSource("Expected an HTTP(S) URL without embedded credentials")
    host = parsed.hostname.lower().rstrip(".")
    if host not in {h.lower().rstrip('.') for h in allowed_hosts}:
        raise UnsafeSource("Host is not explicitly trusted: pass --allow-host HOST")
    if parsed.scheme == "http" and not allow_private:
        raise UnsafeSource("Plain HTTP is restricted to explicit local test mode")
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnsafeSource(f"Host cannot be resolved: {host}") from exc
    if not addresses:
        raise UnsafeSource("No address available")
    for a in addresses:
        try:
            addr = ipaddress.ip_address(a[4][0])
        except ValueError as exc:
            raise UnsafeSource("Unrecognized host address") from exc
        if not addr.is_global and not allow_private:
            raise UnsafeSource("Private, loopback or reserved destinations are blocked")
    # Explicit host allowlists are a trust boundary, not protection against DNS rebinding.
