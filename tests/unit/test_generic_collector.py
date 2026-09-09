import httpx
import pytest

from pricewatch.collectors.generic import GenericStructuredDataCollector
from pricewatch.domain.models import CollectError, CollectRequest, OfferSnapshot
from pricewatch.net.http_client import SecureHttpClient

PRODUCT_HTML = b"""
<script type="application/ld+json">
{"@type": "Product", "name": "Item", "offers": {"@type": "Offer", "price": "10.00", "priceCurrency": "BRL"}}
</script>
"""


def fake_resolver(hostname: str, port: int) -> str:
    return "93.184.216.34"


@pytest.mark.asyncio
async def test_generic_collector_returns_offer_snapshot() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=PRODUCT_HTML, headers={"content-type": "text/html"})

    http_client = SecureHttpClient(resolver=fake_resolver, transport=httpx.MockTransport(handler))
    collector = GenericStructuredDataCollector(http_client)

    result = await collector.collect(CollectRequest(url="https://shop.example/product"))

    assert isinstance(result, OfferSnapshot)
    assert result.price.currency == "BRL"


@pytest.mark.asyncio
async def test_generic_collector_maps_blocked_url_to_collect_error() -> None:
    http_client = SecureHttpClient()
    collector = GenericStructuredDataCollector(http_client)

    result = await collector.collect(CollectRequest(url="http://127.0.0.1/admin"))

    assert isinstance(result, CollectError)
    assert result.code == "blocked_url"
    assert result.retryable is False


@pytest.mark.asyncio
async def test_generic_collector_maps_http_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    http_client = SecureHttpClient(resolver=fake_resolver, transport=httpx.MockTransport(handler))
    collector = GenericStructuredDataCollector(http_client)

    result = await collector.collect(CollectRequest(url="https://shop.example/missing"))

    assert isinstance(result, CollectError)
    assert result.code == "http_error"
    assert result.retryable is False


def test_generic_collector_supports_any_http_url() -> None:
    collector = GenericStructuredDataCollector(SecureHttpClient())

    assert collector.supports("https://any-shop.example/product")
    assert not collector.supports("ftp://shop.example/product")
