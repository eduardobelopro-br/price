import httpx
import pytest

from pricewatch.collectors.demo import DemoCollector
from pricewatch.collectors.generic import GenericStructuredDataCollector
from pricewatch.collectors.registry import CollectorRegistry
from pricewatch.domain.models import CollectError, CollectRequest, OfferSnapshot
from pricewatch.net.http_client import SecureHttpClient

PRODUCT_HTML = b"""
<script type="application/ld+json">
{"@type": "Product", "name": "Item", "offers": {"@type": "Offer", "price": "10.00", "priceCurrency": "BRL"}}
</script>
"""


def fake_resolver(hostname: str, port: int) -> str:
    return "93.184.216.34"


def make_registry() -> CollectorRegistry:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=PRODUCT_HTML, headers={"content-type": "text/html"})

    http_client = SecureHttpClient(resolver=fake_resolver, transport=httpx.MockTransport(handler))
    return CollectorRegistry([DemoCollector(), GenericStructuredDataCollector(http_client)])


@pytest.mark.asyncio
async def test_registry_routes_demo_url_to_demo_collector() -> None:
    registry = make_registry()

    result = await registry.collect(CollectRequest(url="https://demo.pricewatch.invalid/x"))

    assert isinstance(result, OfferSnapshot)
    assert result.source_kind == "demo"


@pytest.mark.asyncio
async def test_registry_routes_real_url_to_generic_collector() -> None:
    registry = make_registry()

    result = await registry.collect(CollectRequest(url="https://shop.example/product"))

    assert isinstance(result, OfferSnapshot)
    assert result.source_kind == "real"


@pytest.mark.asyncio
async def test_registry_returns_unsupported_for_unsupported_scheme() -> None:
    registry = make_registry()

    result = await registry.collect(CollectRequest(url="ftp://shop.example/product"))

    assert isinstance(result, CollectError)
    assert result.code == "unsupported"
