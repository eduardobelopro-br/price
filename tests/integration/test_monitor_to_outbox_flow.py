from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pricewatch.clock import Clock
from pricewatch.collectors.registry import CollectorRegistry
from pricewatch.domain.models import (
    CollectRequest,
    CollectResult,
    Money,
    OfferSnapshot,
    Product,
    Rule,
)
from pricewatch.services.monitor import MonitorService
from pricewatch.storage.sqlite import SqliteStorage


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class ScriptedCollector:
    """Returns a scripted sequence of prices, simulating a real store whose
    price drops between two checks.
    """

    name = "scripted"

    def __init__(self, prices: list[str]) -> None:
        self._prices = iter(prices)

    def supports(self, url: str) -> bool:
        return True

    async def collect(self, request: CollectRequest) -> CollectResult:
        return OfferSnapshot(
            price=Money(Decimal(next(self._prices)), "BRL"), source=self.name, source_kind="demo"
        )


@pytest.fixture
def storage(tmp_path):
    with SqliteStorage(tmp_path / "price.db") as store:
        yield store


@pytest.mark.asyncio
async def test_price_drop_across_two_checks_creates_alert_and_outbox_item(
    storage: SqliteStorage,
) -> None:
    now = datetime.now(UTC)
    product = storage.create_product(
        Product(
            url="https://demo.pricewatch.invalid/x",
            check_interval_seconds=3600,
            next_check_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    storage.add_rule(
        Rule(product_id=product.id, kind="absolute_drop", threshold=Decimal("10.00"), created_at=now)
    )
    clock: Clock = FixedClock(now)
    registry = CollectorRegistry([ScriptedCollector(["100.00", "80.00"])])
    monitor = MonitorService(storage, registry, clock, jitter_max_seconds=0)

    await monitor.check(product)  # first observation: establishes the baseline, no drop yet
    await monitor.check(storage.get_product(product.id))  # second: drops by 20.00

    assert len(storage.list_snapshots(product.id)) == 2
    due_outbox = storage.due_outbox(now)
    assert len(due_outbox) == 1
    assert due_outbox[0].channel == "telegram"


@pytest.mark.asyncio
async def test_same_price_drop_repeated_after_recovery_creates_a_second_alert(
    storage: SqliteStorage,
) -> None:
    """Fase 6.3 regression: a price-based idempotency key would have
    blocked this second, legitimate alert at the same price point.
    """
    now = datetime.now(UTC)
    product = storage.create_product(
        Product(
            url="https://demo.pricewatch.invalid/y",
            check_interval_seconds=3600,
            next_check_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    storage.add_rule(
        Rule(product_id=product.id, kind="absolute_drop", threshold=Decimal("10.00"), created_at=now)
    )
    clock = FixedClock(now)
    registry = CollectorRegistry([ScriptedCollector(["100.00", "80.00", "110.00", "80.00"])])
    monitor = MonitorService(storage, registry, clock, jitter_max_seconds=0)

    product = (await monitor.check(product)).product  # 100.00: baseline
    product = (await monitor.check(product)).product  # 80.00: drop -> alert 1
    clock._now = now + timedelta(hours=1)
    product = (await monitor.check(product)).product  # 110.00: recovers
    clock._now = now + timedelta(hours=2)
    await monitor.check(product)  # 80.00 again: a new drop -> alert 2

    alerts = storage.list_alert_events(product_id=product.id, limit=10)
    assert len(alerts) == 2
