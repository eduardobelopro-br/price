from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta

from pricewatch.clock import Clock
from pricewatch.collectors.registry import CollectorRegistry
from pricewatch.domain.models import (
    CollectError,
    CollectionAttempt,
    CollectRequest,
    OfferSnapshot,
    OutboxItem,
    Product,
)
from pricewatch.services.rules import RulesEngine
from pricewatch.storage.base import Storage

NOTIFICATION_CHANNEL_TELEGRAM = "telegram"


@dataclass(frozen=True, slots=True)
class MonitorOutcome:
    product: Product
    result: OfferSnapshot | CollectError


class MonitorService:
    """Orchestrates a single check: collect an offer, persist the attempt and
    (on success) the snapshot, and reschedule the product's next check with
    backoff on failure and jitter in both cases.
    """

    def __init__(
        self,
        storage: Storage,
        registry: CollectorRegistry,
        clock: Clock,
        *,
        rules_engine: RulesEngine | None = None,
        backoff_base_seconds: int = 60,
        backoff_max_seconds: int = 6 * 3600,
        jitter_max_seconds: int = 120,
    ) -> None:
        self._storage = storage
        self._registry = registry
        self._clock = clock
        self._rules_engine = rules_engine or RulesEngine(storage)
        self._backoff_base_seconds = backoff_base_seconds
        self._backoff_max_seconds = backoff_max_seconds
        self._jitter_max_seconds = jitter_max_seconds

    async def check(self, product: Product) -> MonitorOutcome:
        request = CollectRequest(url=product.url, variant_key=product.variant_key)
        result = await self._registry.collect(request)

        if isinstance(result, OfferSnapshot):
            updated = self.record_success(product, result)
        else:
            updated = self.record_failure(product, result)

        return MonitorOutcome(product=updated, result=result)

    def record_success(self, product: Product, snapshot: OfferSnapshot) -> Product:
        assert product.id is not None
        now = self._clock.now()

        self._storage.add_snapshot(product.id, snapshot)
        self._storage.add_collection_attempt(
            CollectionAttempt(
                product_id=product.id,
                collector=snapshot.source,
                status="success",
                observed_at=now,
            )
        )

        product.consecutive_failures = 0
        product.next_check_at = now + timedelta(
            seconds=product.check_interval_seconds + self._jitter_seconds()
        )
        product.updated_at = now
        updated = self._storage.update_product(product)

        for event in self._rules_engine.evaluate_product(updated, now):
            assert event.id is not None
            self._storage.enqueue_outbox(
                OutboxItem(
                    alert_event_id=event.id,
                    channel=NOTIFICATION_CHANNEL_TELEGRAM,
                    next_attempt_at=now,
                    created_at=now,
                )
            )

        return updated

    def record_failure(self, product: Product, error: CollectError) -> Product:
        assert product.id is not None
        now = self._clock.now()

        self._storage.add_collection_attempt(
            CollectionAttempt(
                product_id=product.id,
                collector=error.collector,
                status="error",
                error_code=error.code,
                error_message=error.message,
                observed_at=now,
            )
        )

        product.consecutive_failures += 1
        if not error.retryable:
            product.status = "unsupported"
            product.next_check_at = now + timedelta(seconds=self._backoff_max_seconds)
        else:
            backoff = self._compute_backoff(product.consecutive_failures)
            product.next_check_at = now + timedelta(seconds=backoff + self._jitter_seconds())
        product.updated_at = now
        return self._storage.update_product(product)

    def _compute_backoff(self, consecutive_failures: int) -> int:
        exponent = min(max(consecutive_failures - 1, 0), 10)
        seconds = self._backoff_base_seconds * (2**exponent)
        return min(int(seconds), self._backoff_max_seconds)

    def _jitter_seconds(self) -> float:
        return random.uniform(0, self._jitter_max_seconds)
