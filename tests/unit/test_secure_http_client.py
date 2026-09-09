import httpx
import pytest

from pricewatch.net.http_client import FetchError, SecureHttpClient
from pricewatch.net.url_safety import resolve_pinned_ip

PUBLIC_IP = "93.184.216.34"


def fake_resolver(hostname: str, port: int) -> str:
    """Pretends "shop.example" resolves to a public IP, but still runs real
    safety validation for any other host (e.g. an IP literal from a
    redirect), so tests can prove unsafe redirect targets are rejected
    without depending on real DNS/network access.
    """
    if hostname == "shop.example":
        return PUBLIC_IP
    return resolve_pinned_ip(hostname, port)


@pytest.mark.asyncio
async def test_fetch_returns_body_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"hello", headers={"content-type": "text/plain"})

    client = SecureHttpClient(
        resolver=fake_resolver, transport=httpx.MockTransport(handler)
    )

    result = await client.fetch("https://shop.example/product")

    assert result.status_code == 200
    assert result.body == b"hello"


@pytest.mark.asyncio
async def test_fetch_follows_redirect_to_safe_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(302, headers={"location": "https://shop.example/new"})
        return httpx.Response(200, content=b"final")

    client = SecureHttpClient(
        resolver=fake_resolver, transport=httpx.MockTransport(handler)
    )

    result = await client.fetch("https://shop.example/old")

    assert result.body == b"final"
    assert result.final_url == "https://shop.example/new"


@pytest.mark.asyncio
async def test_fetch_rejects_redirect_to_private_ip() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://10.0.0.5/internal"})

    client = SecureHttpClient(
        resolver=fake_resolver, transport=httpx.MockTransport(handler)
    )

    with pytest.raises(Exception, match="disallowed address"):
        await client.fetch("https://shop.example/old")


@pytest.mark.asyncio
async def test_fetch_enforces_max_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://shop.example/loop"})

    client = SecureHttpClient(
        resolver=fake_resolver, transport=httpx.MockTransport(handler), max_redirects=2
    )

    with pytest.raises(FetchError, match="too many redirects"):
        await client.fetch("https://shop.example/loop")


@pytest.mark.asyncio
async def test_fetch_enforces_max_response_bytes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 100)

    client = SecureHttpClient(
        resolver=fake_resolver, transport=httpx.MockTransport(handler), max_response_bytes=10
    )

    with pytest.raises(FetchError, match="exceeded max size"):
        await client.fetch("https://shop.example/big")
