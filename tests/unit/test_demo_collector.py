import pytest

from pricewatch.collectors.demo import DemoCollector
from pricewatch.domain.models import CollectRequest, OfferSnapshot


@pytest.mark.asyncio
async def test_demo_collector_is_deterministic() -> None:
    collector = DemoCollector()
    req = CollectRequest("https://demo.pricewatch.invalid/product/alpha")
    a = await collector.collect(req)
    b = await collector.collect(req)
    assert isinstance(a, OfferSnapshot)
    assert isinstance(b, OfferSnapshot)
    assert a.price == b.price
    assert a.source_kind == "demo"
