from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeEndpoint(ValueError):
    pass


def validate_endpoint(url: str) -> str:
    """Reject URLs that point at private/internal hosts to prevent SSRF.

    The user-supplied endpoint is dialled from our server, so without this check
    anyone could probe our internal network or localhost.

    Residual risk: this performs a check-time `getaddrinfo`, but httpx
    re-resolves on connect — a hostile DNS server with TTL=0 could rebind
    between the check and the actual probe call. Mitigations elsewhere:
    `follow_redirects=False` in `runner.py`, plus the systemd unit runs as a
    non-root user with no access to cloud metadata. A proper fix is a custom
    httpx transport that connects by pre-validated IP with SNI preservation —
    left as future work.
    """
    if not isinstance(url, str) or len(url) > 1024:
        raise UnsafeEndpoint("endpoint URL is missing or absurdly long")
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeEndpoint("endpoint must use http:// or https://")
    host = parsed.hostname
    if not host:
        raise UnsafeEndpoint("endpoint is missing a hostname")
    if host.lower() in {"localhost", "ip6-localhost", "ip6-loopback"}:
        raise UnsafeEndpoint("endpoint points at localhost")

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeEndpoint(f"could not resolve hostname: {host}") from exc

    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeEndpoint(f"endpoint resolves to a non-public address: {addr}")

    return url.strip().rstrip("/")
