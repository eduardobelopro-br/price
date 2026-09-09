from datetime import UTC, datetime, timedelta

import pytest

from pricewatch.clock import Clock
from pricewatch.collectors.demo import DemoCollector
from pricewatch.collectors.registry import CollectorRegistry
from pricewatch.domain.models import CollectRequest, CollectResult, Product
from pricewatch.services.monitor import MonitorService
from pricewatch.storage.sqlite import SqliteStorage
from pricewatch.worker.scheduler import Worker


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class ExplodingCollector:
    name = "exploding"

    def supports(self, url: str) -> bool:
        return True

    async def collect(self, request: CollectRequest) -> CollectResult:
        raise RuntimeError("collector bug")


def make_due_product(storage: SqliteStorage, now: datetime, url: str) -> Product:
    return storage.create_product(
        Product(
            url=url,
            check_interval_seconds=3600,
            next_check_at=now - timedelta(seconds=1),
            created_at=now,
            updated_at=now,
        )
    )


@pytest.fixture
def storage(tmp_path):
    with SqliteStorage(tmp_path / "price.db") as store:
        yield store


@pytest.mark.asyncio
async def test_run_once_checks_all_due_products(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    make_due_product(storage, now, "https://demo.pricewatch.invalid/a")
    make_due_product(storage, now, "https://demo.pricewatch.invalid/b")
    clock: Clock = FixedClock(now)
    monitor = MonitorService(storage, CollectorRegistry([DemoCollector()]), clock, jitter_max_seconds=0)
    worker = Worker(storage, monitor, clock)

    checked = await worker.run_once()

    assert checked == 2
    assert all(
        len(storage.list_snapshots(p.id)) == 1 for p in storage.list_products()
    )


@pytest.mark.asyncio
async def test_run_once_returns_zero_when_nothing_is_due(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    clock: Clock = FixedClock(now)
    monitor = MonitorService(storage, CollectorRegistry([DemoCollector()]), clock)
    worker = Worker(storage, monitor, clock)

    assert await worker.run_once() == 0


@pytest.mark.asyncio
async def test_unexpected_exception_in_one_product_does_not_abort_the_batch(
    storage: SqliteStorage,
) -> None:
    now = datetime.now(UTC)
    broken = make_due_product(storage, now, "https://demo.pricewatch.invalid/broken")
    healthy = make_due_product(storage, now, "https://other.pricewatch.invalid/ok")
    clock: Clock = FixedClock(now)
    registry = CollectorRegistry([ExplodingCollector()])
    monitor = MonitorService(storage, registry, clock, jitter_max_seconds=0)
    worker = Worker(storage, monitor, clock)

    checked = await worker.run_once()

    assert checked == 2
    broken_after = storage.get_product(broken.id)
    healthy_after = storage.get_product(healthy.id)
    assert broken_after.consecutive_failures == 1
    assert healthy_after.consecutive_failures == 1
    assert storage.list_snapshots(broken.id) == []
