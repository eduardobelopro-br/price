from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pricewatch.domain.models import (
    AlertEvent,
    CollectionAttempt,
    Money,
    OfferSnapshot,
    Product,
    Rule,
)
from pricewatch.storage.sqlite import SqliteStorage


def make_product(url: str = "https://demo.pricewatch.invalid/x") -> Product:
    now = datetime.now(UTC)
    return Product(
        url=url,
        check_interval_seconds=3600,
        next_check_at=now,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def storage(tmp_path):
    with SqliteStorage(tmp_path / "price.db") as store:
        yield store


def test_create_and_get_product(storage: SqliteStorage) -> None:
    created = storage.create_product(make_product())

    assert created.id is not None
    assert storage.get_product(created.id).url == created.url


def test_snapshots_are_append_only(storage: SqliteStorage) -> None:
    product = storage.create_product(make_product())
    snapshot = OfferSnapshot(
        price=Money(Decimal("10.00"), "BRL"),
        source="demo",
        source_kind="demo",
    )

    storage.add_snapshot(product.id, snapshot)
    storage.add_snapshot(product.id, snapshot)

    assert len(storage.list_snapshots(product.id)) == 2


def test_collection_failure_does_not_create_zero_price_snapshot(storage: SqliteStorage) -> None:
    product = storage.create_product(make_product())
    attempt = CollectionAttempt(
        product_id=product.id,
        collector="demo",
        status="error",
        error_code="unsupported",
        error_message="URL is not a demo URL",
        observed_at=datetime.now(UTC),
    )

    storage.add_collection_attempt(attempt)

    assert storage.list_snapshots(product.id) == []
    assert storage.last_snapshot(product.id) is None


def test_alert_event_idempotency_key_is_unique(storage: SqliteStorage) -> None:
    product = storage.create_product(make_product())
    now = datetime.now(UTC)
    rule = storage.add_rule(
        Rule(product_id=product.id, kind="target_price", threshold=Decimal("19.90"), created_at=now)
    )
    event = AlertEvent(
        product_id=product.id,
        rule_id=rule.id,
        idempotency_key="product-1:target_price:19.90",
        reference_price=Decimal("29.90"),
        current_price=Decimal("19.90"),
        currency="BRL",
        created_at=now,
    )

    first = storage.create_alert_event(event)
    duplicate = storage.create_alert_event(event)

    assert first is not None
    assert duplicate is None


def test_due_products_respects_next_check_at(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    due = storage.create_product(make_product("https://demo.pricewatch.invalid/due"))
    due.next_check_at = now - timedelta(seconds=1)
    storage.update_product(due)

    not_due = storage.create_product(make_product("https://demo.pricewatch.invalid/not-due"))
    not_due.next_check_at = now + timedelta(hours=1)
    storage.update_product(not_due)

    result = storage.due_products(now)

    assert [p.id for p in result] == [due.id]


def test_data_survives_reopening_the_same_database(tmp_path) -> None:
    db_path = tmp_path / "price.db"

    with SqliteStorage(db_path) as store:
        product = store.create_product(make_product())
        store.add_snapshot(
            product.id,
            OfferSnapshot(price=Money(Decimal("10.00"), "BRL"), source="demo", source_kind="demo"),
        )

    with SqliteStorage(db_path) as reopened:
        restored = reopened.get_product_by_url("https://demo.pricewatch.invalid/x")
        assert restored is not None
        assert len(reopened.list_snapshots(restored.id)) == 1
