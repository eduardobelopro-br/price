from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

DEFAULT_ALLOWED_PORTS: frozenset[int] = frozenset({80, 443})
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})


class UrlSafetyError(ValueError):
    pass


def validate_scheme_and_credentials(url: str) -> str:
    """Validates scheme and credentials, returning the hostname."""
    parts = urlsplit(url)
    if parts.scheme not in ALLOWED_SCHEMES:
        raise UrlSafetyError(f"unsupported scheme: {parts.scheme!r}")
    if parts.username or parts.password:
        raise UrlSafetyError("URLs with embedded credentials are not allowed")
    if not parts.hostname:
        raise UrlSafetyError("URL has no hostname")
    return parts.hostname


def validate_port(port: int, allowed_ports: frozenset[int] = DEFAULT_ALLOWED_PORTS) -> None:
    if port not in allowed_ports:
        raise UrlSafetyError(f"port not allowed: {port}")


def is_safe_ip(ip: IPAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip.is_loopback or ip.is_private or ip.is_link_local:
        return False
    if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return False
    return bool(ip.is_global)


def resolve_pinned_ip(hostname: str, port: int) -> str:
    """Resolves a hostname, rejects it unless every address it resolves to is
    public, and returns one safe address to connect to directly.

    Pinning the connection to an address validated here (rather than letting
    the HTTP client resolve the hostname again at connect time) closes the
    DNS-rebinding window between validation and the actual TCP connection.
    """
    try:
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UrlSafetyError(f"could not resolve host: {hostname}") from exc

    resolved_ips = {str(info[4][0]) for info in addr_info}
    if not resolved_ips:
        raise UrlSafetyError(f"host does not resolve to any address: {hostname}")

    for raw_ip in resolved_ips:
        ip = ipaddress.ip_address(raw_ip.split("%")[0])
        if not is_safe_ip(ip):
            raise UrlSafetyError(f"host resolves to a disallowed address: {hostname} -> {raw_ip}")

    return next(iter(resolved_ips))
