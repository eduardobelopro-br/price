from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from pricewatch.net.url_safety import (
    DEFAULT_ALLOWED_PORTS,
    UrlSafetyError,
    resolve_pinned_ip,
    validate_port,
    validate_scheme_and_credentials,
)

_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
DEFAULT_USER_AGENT = "PriceWatchBot/0.1 (+https://github.com/pricewatch/pricewatch)"


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FetchResult:
    status_code: int
    body: bytes
    content_type: str | None
    final_url: str


@dataclass(frozen=True, slots=True)
class _PinnedTarget:
    scheme: str
    hostname: str
    port: int
    ip: str
    path_and_query: str


def _resolve_target(
    url: str,
    allowed_ports: frozenset[int],
    resolver: Callable[[str, int], str],
) -> _PinnedTarget:
    hostname = validate_scheme_and_credentials(url)
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    validate_port(port, allowed_ports)
    ip = resolver(hostname, port)

    path_and_query = parts.path or "/"
    if parts.query:
        path_and_query = f"{path_and_query}?{parts.query}"

    return _PinnedTarget(
        scheme=parts.scheme, hostname=hostname, port=port, ip=ip, path_and_query=path_and_query
    )


class SecureHttpClient:
    """HTTP client with SSRF hardening: only http/https, only allow-listed
    ports, DNS resolution pinned to validated public addresses, bounded
    redirects (each hop re-validated), bounded response size, and bounded
    timeouts.
    """

    def __init__(
        self,
        *,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 10.0,
        max_redirects: int = 3,
        max_response_bytes: int = 3_000_000,
        allowed_ports: frozenset[int] = DEFAULT_ALLOWED_PORTS,
        user_agent: str = DEFAULT_USER_AGENT,
        resolver: Callable[[str, int], str] = resolve_pinned_ip,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=read_timeout_seconds,
            pool=connect_timeout_seconds,
        )
        self._max_redirects = max_redirects
        self._max_response_bytes = max_response_bytes
        self._allowed_ports = allowed_ports
        self._user_agent = user_agent
        self._resolver = resolver
        self._transport = transport

    async def fetch(self, url: str) -> FetchResult:
        current_url = url
        async with httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport, follow_redirects=False
        ) as client:
            for _ in range(self._max_redirects + 1):
                target = _resolve_target(current_url, self._allowed_ports, self._resolver)
                pinned_url = f"{target.scheme}://{target.ip}:{target.port}{target.path_and_query}"
                headers = {
                    "Host": target.hostname,
                    "User-Agent": self._user_agent,
                    "Accept": "text/html,application/ld+json;q=0.9,*/*;q=0.5",
                }
                extensions = (
                    {"sni_hostname": target.hostname} if target.scheme == "https" else {}
                )
                request = client.build_request(
                    "GET", pinned_url, headers=headers, extensions=extensions
                )

                try:
                    response = await client.send(request, stream=True)
                except httpx.HTTPError as exc:
                    raise FetchError(f"request failed: {exc}") from exc

                try:
                    if response.status_code in _REDIRECT_STATUS_CODES:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError("redirect response without Location header")
                        current_url = str(httpx.URL(current_url).join(location))
                        continue

                    body = await self._read_body(response)
                    return FetchResult(
                        status_code=response.status_code,
                        body=body,
                        content_type=response.headers.get("content-type"),
                        final_url=current_url,
                    )
                finally:
                    await response.aclose()

        raise FetchError(f"too many redirects (limit={self._max_redirects})")

    async def _read_body(self, response: httpx.Response) -> bytes:
        chunks = bytearray()
        async for chunk in response.aiter_bytes():
            chunks.extend(chunk)
            if len(chunks) > self._max_response_bytes:
                raise FetchError(
                    f"response exceeded max size of {self._max_response_bytes} bytes"
                )
        return bytes(chunks)


__all__ = ["FetchError", "FetchResult", "SecureHttpClient", "UrlSafetyError"]
