from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pricewatch.domain.models import AlertEvent, OfferSnapshot, Product, Rule
from pricewatch.services.comparison import comparable
from pricewatch.storage.base import Storage


class RulesEngine:
    """Compares the latest observation against a valid reference and creates
    idempotent alert events. A rule only fires on a meaningful change (a
    fresh price, or a fresh false->true transition for target_price), so it
    never spams the same condition while the price stays put.
    """

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def evaluate_product(self, product: Product, now: datetime) -> list[AlertEvent]:
        assert product.id is not None
        current = self._storage.last_snapshot(product.id)
        if current is None:
            return []

        history = sorted(
            (
                snapshot
                for snapshot in self._storage.list_snapshots(product.id)
                if snapshot.observed_at < current.observed_at and comparable(current, snapshot)
            ),
            key=lambda snapshot: snapshot.observed_at,
        )
        previous = history[-1] if history else None

        events: list[AlertEvent] = []
        for rule in self._storage.list_rules(product.id):
            if not rule.active or not self._fires(rule, current, previous, history):
                continue

            assert rule.id is not None
            event = self._storage.create_alert_event(
                AlertEvent(
                    product_id=product.id,
                    rule_id=rule.id,
                    idempotency_key=self._idempotency_key(product.id, rule, current),
                    reference_price=(previous or current).price.amount,
                    current_price=current.price.amount,
                    currency=current.price.currency,
                    created_at=now,
                )
            )
            if event is not None:
                events.append(event)

        return events

    def _fires(
        self,
        rule: Rule,
        current: OfferSnapshot,
        previous: OfferSnapshot | None,
        history: list[OfferSnapshot],
    ) -> bool:
        if rule.kind == "target_price":
            # Only observations made after the rule existed count as "already
            # triggered" — otherwise a rule created while the price already
            # sat below the target would never fire its first alert.
            reference = next(
                (s for s in reversed(history) if s.observed_at >= rule.created_at), None
            )
            currently = current.price.amount <= rule.threshold
            previously = reference is not None and reference.price.amount <= rule.threshold
            return currently and not previously

        if previous is None:
            return False

        if rule.kind == "absolute_drop":
            drop = previous.price.amount - current.price.amount
            return drop >= rule.threshold

        if rule.kind == "percentage_drop":
            if previous.price.amount == 0:
                return False
            drop = previous.price.amount - current.price.amount
            percentage = (drop / previous.price.amount) * Decimal(100)
            return percentage >= rule.threshold

        if rule.kind == "new_low":
            if not history:
                return False
            lowest = min(snapshot.price.amount for snapshot in history)
            return current.price.amount < lowest

        return False

    @staticmethod
    def _idempotency_key(product_id: int, rule: Rule, current: OfferSnapshot) -> str:
        return f"{product_id}:{rule.id}:{rule.kind}:{current.price.amount}:{current.price.currency}"
