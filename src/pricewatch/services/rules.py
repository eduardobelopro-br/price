from __future__ import annotations

from decimal import Decimal

from pricewatch.domain.models import AlertCandidate, OfferSnapshot, Product, Rule, StoredSnapshot
from pricewatch.services.comparison import comparable
from pricewatch.storage.base import Storage


class RulesEngine:
    """Compares the latest observation against a valid reference and
    returns the rules that fired as AlertCandidate values. Pure with
    respect to storage: it only reads. Persisting a candidate (and
    guaranteeing it is not a duplicate) is the caller's responsibility,
    via Storage.create_alert_with_outbox.
    """

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def evaluate_product(self, product: Product) -> list[AlertCandidate]:
        assert product.id is not None
        current = self._storage.last_snapshot(product.id)
        if current is None:
            return []

        history = sorted(
            (
                stored
                for stored in self._storage.list_snapshots(product.id)
                if stored.offer.observed_at < current.offer.observed_at
                and comparable(current.offer, stored.offer)
            ),
            key=lambda stored: stored.offer.observed_at,
        )
        previous = history[-1] if history else None

        candidates: list[AlertCandidate] = []
        for rule in self._storage.list_rules(product.id):
            if not rule.active or not self._fires(rule, current.offer, previous, history):
                continue

            assert rule.id is not None
            candidates.append(
                AlertCandidate(
                    product_id=product.id,
                    rule_id=rule.id,
                    snapshot_id=current.id,
                    reference_price=(previous.offer if previous else current.offer).price.amount,
                    current_price=current.offer.price.amount,
                    currency=current.offer.price.currency,
                )
            )

        return candidates

    def _fires(
        self,
        rule: Rule,
        current: OfferSnapshot,
        previous: StoredSnapshot | None,
        history: list[StoredSnapshot],
    ) -> bool:
        if rule.kind == "target_price":
            # Only observations made after the rule existed count as "already
            # triggered" — otherwise a rule created while the price already
            # sat below the target would never fire its first alert.
            reference = next(
                (s for s in reversed(history) if s.offer.observed_at >= rule.created_at), None
            )
            currently = current.price.amount <= rule.threshold
            previously = reference is not None and reference.offer.price.amount <= rule.threshold
            return currently and not previously

        if previous is None:
            return False

        if rule.kind == "absolute_drop":
            drop = previous.offer.price.amount - current.price.amount
            return drop >= rule.threshold

        if rule.kind == "percentage_drop":
            if previous.offer.price.amount == 0:
                return False
            drop = previous.offer.price.amount - current.price.amount
            percentage = (drop / previous.offer.price.amount) * Decimal(100)
            return percentage >= rule.threshold

        if rule.kind == "new_low":
            if not history:
                return False
            lowest = min(stored.offer.price.amount for stored in history)
            return current.price.amount < lowest

        return False
