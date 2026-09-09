import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pricewatch.domain.models import AlertEvent, Product, Rule
from pricewatch.storage.sqlite import SqliteStorage


@pytest.fixture
def storage(tmp_path):
    with SqliteStorage(tmp_path / "price.db") as store:
        yield store


def make_product_and_rule(storage: SqliteStorage, now: datetime) -> tuple[int, int]:
    product = storage.create_product(
        Product(
            url="https://demo.pricewatch.invalid/x",
            check_interval_seconds=3600,
            next_check_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    rule = storage.add_rule(
        Rule(product_id=product.id, kind="absolute_drop", threshold=Decimal("10.00"), created_at=now)
    )
    return product.id, rule.id


def make_event(product_id: int, rule_id: int, idempotency_key: str, now: datetime) -> AlertEvent:
    return AlertEvent(
        product_id=product_id,
        rule_id=rule_id,
        idempotency_key=idempotency_key,
        reference_price=Decimal("100.00"),
        current_price=Decimal("80.00"),
        currency="BRL",
        created_at=now,
    )


def test_alert_event_and_outbox_are_created_atomically(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product_id, rule_id = make_product_and_rule(storage, now)
    event = make_event(product_id, rule_id, "k1", now)

    created = storage.create_alert_with_outbox(
        event, channel="telegram", next_attempt_at=now, created_at=now
    )

    assert created is not None
    assert created.id is not None
    outbox_items = storage.list_outbox_for_event(created.id)
    assert len(outbox_items) == 1
    assert outbox_items[0].alert_event_id == created.id
    assert outbox_items[0].status == "pending"


def test_reprocessing_the_same_snapshot_is_idempotent(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product_id, rule_id = make_product_and_rule(storage, now)
    event = make_event(product_id, rule_id, "product:rule:snapshot-42", now)

    first = storage.create_alert_with_outbox(
        event, channel="telegram", next_attempt_at=now, created_at=now
    )
    second = storage.create_alert_with_outbox(
        event, channel="telegram", next_attempt_at=now, created_at=now
    )

    assert first is not None
    assert second is None
    assert len(storage.list_alert_events(product_id=product_id, limit=10)) == 1


def test_key_conflict_does_not_create_an_extra_outbox_row(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product_id, rule_id = make_product_and_rule(storage, now)
    event = make_event(product_id, rule_id, "product:rule:snapshot-42", now)

    created = storage.create_alert_with_outbox(
        event, channel="telegram", next_attempt_at=now, created_at=now
    )
    storage.create_alert_with_outbox(event, channel="telegram", next_attempt_at=now, created_at=now)

    assert created is not None
    assert len(storage.list_outbox_for_event(created.id)) == 1


def test_same_price_in_a_new_transition_can_alert_again(storage: SqliteStorage) -> None:
    """The bug this phase fixes: a price-based idempotency key would block
    a legitimate later alert at the same price. Keying on the triggering
    snapshot's id instead means a later, distinct snapshot with the same
    price is free to alert again.
    """
    now = datetime.now(UTC)
    product_id, rule_id = make_product_and_rule(storage, now)

    first_drop = make_event(product_id, rule_id, f"{product_id}:{rule_id}:snapshot-1", now)
    first = storage.create_alert_with_outbox(
        first_drop, channel="telegram", next_attempt_at=now, created_at=now
    )

    later = now + timedelta(hours=1)
    second_drop = make_event(product_id, rule_id, f"{product_id}:{rule_id}:snapshot-99", later)
    second = storage.create_alert_with_outbox(
        second_drop, channel="telegram", next_attempt_at=later, created_at=later
    )

    assert first is not None
    assert second is not None
    assert first.id != second.id
    assert len(storage.list_alert_events(product_id=product_id, limit=10)) == 2


class _FailingOutboxInsertConnection:
    """Wraps a real sqlite3.Connection, forwarding everything except
    injecting a failure into the outbox INSERT — simulating a crash (or
    disk error) between the two inserts of create_alert_with_outbox.
    """

    def __init__(self, real_connection: sqlite3.Connection) -> None:
        self._real = real_connection

    def execute(self, sql: str, *args: object, **kwargs: object) -> sqlite3.Cursor:
        if "INSERT INTO outbox" in sql:
            raise sqlite3.IntegrityError("simulated failure between the two inserts")
        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)


def test_a_failure_inserting_the_outbox_row_rolls_back_the_alert_event(
    storage: SqliteStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    product_id, rule_id = make_product_and_rule(storage, now)
    event = make_event(product_id, rule_id, "will-not-survive", now)

    real_connection = storage._connection  # type: ignore[attr-defined]
    monkeypatch.setattr(storage, "_connection", _FailingOutboxInsertConnection(real_connection))

    result = storage.create_alert_with_outbox(
        event, channel="telegram", next_attempt_at=now, created_at=now
    )

    assert result is None
    monkeypatch.setattr(storage, "_connection", real_connection)
    assert storage.get_alert_event_by_key("will-not-survive") is None
