from datetime import UTC, datetime, timedelta

import pytest

from pricewatch.clock import Clock
from pricewatch.collectors.demo import DemoCollector
from pricewatch.collectors.registry import CollectorRegistry
from pricewatch.domain.models import (
    CollectError,
    CollectRequest,
    CollectResult,
    OfferSnapshot,
    Product,
)
from pricewatch.services.monitor import MonitorService
from pricewatch.storage.sqlite import SqliteStorage


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class AlwaysFailsCollector:
    name = "always_fails"

    def supports(self, url: str) -> bool:
        return True

    async def collect(self, request: CollectRequest) -> CollectResult:
        return CollectError(code="fetch_failed", message="boom", collector=self.name, retryable=True)


class UnsupportedCollector:
    name = "unsupported_collector"

    def supports(self, url: str) -> bool:
        return True

    async def collect(self, request: CollectRequest) -> CollectResult:
        return CollectError(code="unsupported", message="nope", collector=self.name, retryable=False)


def make_product(storage: SqliteStorage, now: datetime) -> Product:
    return storage.create_product(
        Product(
            url="https://demo.pricewatch.invalid/x",
            check_interval_seconds=3600,
            next_check_at=now,
            created_at=now,
            updated_at=now,
        )
    )


@pytest.fixture
def storage(tmp_path):
    with SqliteStorage(tmp_path / "price.db") as store:
        yield store


@pytest.mark.asyncio
async def test_successful_check_persists_snapshot_and_reschedules(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    clock: Clock = FixedClock(now)
    monitor = MonitorService(storage, CollectorRegistry([DemoCollector()]), clock, jitter_max_seconds=0)

    outcome = await monitor.check(product)

    assert isinstance(outcome.result, OfferSnapshot)
    assert len(storage.list_snapshots(product.id)) == 1
    assert outcome.product.consecutive_failures == 0
    assert outcome.product.next_check_at == now + timedelta(seconds=3600)


@pytest.mark.asyncio
async def test_retryable_failure_does_not_create_snapshot_and_applies_backoff(
    storage: SqliteStorage,
) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    clock: Clock = FixedClock(now)
    monitor = MonitorService(
        storage,
        CollectorRegistry([AlwaysFailsCollector()]),
        clock,
        backoff_base_seconds=60,
        jitter_max_seconds=0,
    )

    outcome = await monitor.check(product)

    assert isinstance(outcome.result, CollectError)
    assert storage.list_snapshots(product.id) == []
    assert outcome.product.consecutive_failures == 1
    assert outcome.product.status == "active"
    assert outcome.product.next_check_at == now + timedelta(seconds=60)


@pytest.mark.asyncio
async def test_repeated_failures_increase_backoff(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    clock: Clock = FixedClock(now)
    monitor = MonitorService(
        storage,
        CollectorRegistry([AlwaysFailsCollector()]),
        clock,
        backoff_base_seconds=60,
        jitter_max_seconds=0,
    )

    first = await monitor.check(product)
    second = await monitor.check(first.product)

    assert second.product.consecutive_failures == 2
    assert second.product.next_check_at == now + timedelta(seconds=60 * 2)


@pytest.mark.asyncio
async def test_non_retryable_failure_marks_product_unsupported(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    clock: Clock = FixedClock(now)
    monitor = MonitorService(storage, CollectorRegistry([UnsupportedCollector()]), clock)

    outcome = await monitor.check(product)

    assert outcome.product.status == "unsupported"
