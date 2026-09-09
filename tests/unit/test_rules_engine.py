from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pricewatch.domain.models import Money, OfferSnapshot, Product, Rule
from pricewatch.services.rules import RulesEngine
from pricewatch.storage.sqlite import SqliteStorage


@pytest.fixture
def storage(tmp_path):
    with SqliteStorage(tmp_path / "price.db") as store:
        yield store


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


def snap(amount: str, observed_at: datetime) -> OfferSnapshot:
    return OfferSnapshot(
        price=Money(Decimal(amount), "BRL"),
        source="demo",
        source_kind="demo",
        observed_at=observed_at,
    )


def test_target_price_fires_on_false_to_true_transition(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    storage.add_snapshot(product.id, snap("100.00", now - timedelta(hours=2)))
    storage.add_snapshot(product.id, snap("50.00", now - timedelta(hours=1)))
    rule = storage.add_rule(
        Rule(product_id=product.id, kind="target_price", threshold=Decimal("80.00"), created_at=now)
    )

    candidates = RulesEngine(storage).evaluate_product(product)

    assert len(candidates) == 1
    assert candidates[0].rule_id == rule.id
    assert candidates[0].current_price == Decimal("50.00")


def test_target_price_does_not_refire_while_still_below_threshold(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    rule_created_at = now - timedelta(hours=2)
    storage.add_rule(
        Rule(
            product_id=product.id,
            kind="target_price",
            threshold=Decimal("80.00"),
            created_at=rule_created_at,
        )
    )
    storage.add_snapshot(product.id, snap("50.00", now - timedelta(hours=1)))
    storage.add_snapshot(product.id, snap("49.00", now))

    candidates = RulesEngine(storage).evaluate_product(product)

    assert candidates == []


def test_target_price_fires_on_first_check_even_if_price_was_already_below_before_rule_existed(
    storage: SqliteStorage,
) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    # The price was already below the target before this rule was ever created.
    storage.add_snapshot(product.id, snap("50.00", now - timedelta(hours=1)))
    storage.add_rule(
        Rule(
            product_id=product.id,
            kind="target_price",
            threshold=Decimal("80.00"),
            created_at=now - timedelta(minutes=30),
        )
    )
    storage.add_snapshot(product.id, snap("49.00", now))

    candidates = RulesEngine(storage).evaluate_product(product)

    assert len(candidates) == 1


def test_absolute_drop_fires_when_drop_meets_threshold(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    storage.add_snapshot(product.id, snap("100.00", now - timedelta(hours=1)))
    storage.add_snapshot(product.id, snap("80.00", now))
    storage.add_rule(
        Rule(product_id=product.id, kind="absolute_drop", threshold=Decimal("15.00"), created_at=now)
    )

    candidates = RulesEngine(storage).evaluate_product(product)

    assert len(candidates) == 1
    assert candidates[0].reference_price == Decimal("100.00")


def test_percentage_drop_fires_when_percentage_meets_threshold(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    storage.add_snapshot(product.id, snap("100.00", now - timedelta(hours=1)))
    storage.add_snapshot(product.id, snap("89.00", now))
    storage.add_rule(
        Rule(product_id=product.id, kind="percentage_drop", threshold=Decimal(10), created_at=now)
    )

    candidates = RulesEngine(storage).evaluate_product(product)

    assert len(candidates) == 1


def test_new_low_fires_only_below_historical_minimum(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    storage.add_snapshot(product.id, snap("100.00", now - timedelta(hours=2)))
    storage.add_snapshot(product.id, snap("90.00", now - timedelta(hours=1)))
    storage.add_snapshot(product.id, snap("95.00", now))
    storage.add_rule(Rule(product_id=product.id, kind="new_low", threshold=Decimal(0), created_at=now))

    candidates = RulesEngine(storage).evaluate_product(product)

    assert candidates == []


def test_evaluate_product_is_pure_and_returns_the_same_candidate_on_repeat_calls(
    storage: SqliteStorage,
) -> None:
    """RulesEngine only reads; it never marks anything as "already alerted"
    itself. Calling it twice for the same stored state must return the same
    candidate both times — deduplication happens when persisting via
    Storage.create_alert_with_outbox, not here.
    """
    now = datetime.now(UTC)
    product = make_product(storage, now)
    storage.add_snapshot(product.id, snap("100.00", now - timedelta(hours=1)))
    storage.add_snapshot(product.id, snap("80.00", now))
    storage.add_rule(
        Rule(product_id=product.id, kind="absolute_drop", threshold=Decimal("15.00"), created_at=now)
    )
    engine = RulesEngine(storage)

    first = engine.evaluate_product(product)
    second = engine.evaluate_product(product)

    assert len(first) == 1
    assert first == second


def test_candidate_carries_the_triggering_snapshot_id_not_just_the_price(
    storage: SqliteStorage,
) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    storage.add_snapshot(product.id, snap("100.00", now - timedelta(hours=1)))
    stored = storage.add_snapshot(product.id, snap("80.00", now))
    storage.add_rule(
        Rule(product_id=product.id, kind="absolute_drop", threshold=Decimal("15.00"), created_at=now)
    )

    candidates = RulesEngine(storage).evaluate_product(product)

    assert candidates[0].snapshot_id == stored.id


def test_inactive_rule_never_fires(storage: SqliteStorage) -> None:
    now = datetime.now(UTC)
    product = make_product(storage, now)
    storage.add_snapshot(product.id, snap("100.00", now - timedelta(hours=1)))
    storage.add_snapshot(product.id, snap("10.00", now))
    storage.add_rule(
        Rule(
            product_id=product.id,
            kind="target_price",
            threshold=Decimal("50.00"),
            created_at=now,
            active=False,
        )
    )

    candidates = RulesEngine(storage).evaluate_product(product)

    assert candidates == []
