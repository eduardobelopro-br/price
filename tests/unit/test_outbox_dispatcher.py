from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from pricewatch.domain.models import AlertEvent, OutboxItem, Product, Rule
from pricewatch.notifications.dispatcher import OutboxDispatcher
from pricewatch.notifications.telegram import TelegramNotifier
from pricewatch.storage.sqlite import SqliteStorage


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


@pytest.fixture
def storage(tmp_path):
    with SqliteStorage(tmp_path / "price.db") as store:
        yield store


def seed_pending_outbox_item(storage: SqliteStorage, now: datetime) -> OutboxItem:
    product = storage.create_product(
        Product(
            url="https://demo.pricewatch.invalid/x",
            title="Produto Demo",
            check_interval_seconds=3600,
            next_check_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    rule = storage.add_rule(
        Rule(product_id=product.id, kind="target_price", threshold=Decimal("50.00"), created_at=now)
    )
    event = storage.create_alert_event(
        AlertEvent(
            product_id=product.id,
            rule_id=rule.id,
            idempotency_key="k1",
            reference_price=Decimal("100.00"),
            current_price=Decimal("45.00"),
            currency="BRL",
            created_at=now,
        )
    )
    return storage.enqueue_outbox(
        OutboxItem(alert_event_id=event.id, channel="telegram", next_attempt_at=now, created_at=now)
    )


@pytest.mark.asyncio
async def test_dispatch_marks_item_as_sent_on_success(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    seed_pending_outbox_item(storage, now)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier("token", "chat", transport=httpx.MockTransport(handler))
    dispatcher = OutboxDispatcher(storage, notifier, FixedClock(now))

    sent = await dispatcher.dispatch_due()

    assert sent == 1
    assert storage.due_outbox(now) == []


@pytest.mark.asyncio
async def test_dispatch_backs_off_before_giving_up_after_max_attempts(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    seed_pending_outbox_item(storage, now)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    notifier = TelegramNotifier("token", "chat", transport=httpx.MockTransport(handler))
    clock = FixedClock(now)
    dispatcher = OutboxDispatcher(storage, notifier, clock, max_attempts=2, retry_backoff_seconds=60)

    await dispatcher.dispatch_due()

    assert storage.due_outbox(now) == []  # rescheduled into the future, not retried immediately
    scheduled = storage.due_outbox(now + timedelta(seconds=61))
    assert len(scheduled) == 1
    assert scheduled[0].status == "pending"
    assert scheduled[0].attempts == 1

    clock._now = now + timedelta(seconds=61)
    await dispatcher.dispatch_due()

    assert storage.due_outbox(now + timedelta(days=1)) == []  # gave up: no longer pending
