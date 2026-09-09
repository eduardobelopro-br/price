from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pricewatch.domain.models import (
    AlertEvent,
    CollectionAttempt,
    OfferSnapshot,
    OutboxItem,
    Product,
    Rule,
    StoredSnapshot,
)


class Storage(Protocol):
    def create_product(self, product: Product) -> Product: ...

    def get_product(self, product_id: int) -> Product | None: ...

    def get_product_by_url(self, url: str) -> Product | None: ...

    def list_products(self) -> list[Product]: ...

    def update_product(self, product: Product) -> Product: ...

    def due_products(self, now: datetime) -> list[Product]: ...

    def add_snapshot(self, product_id: int, snapshot: OfferSnapshot) -> StoredSnapshot: ...

    def last_snapshot(self, product_id: int) -> StoredSnapshot | None: ...

    def list_snapshots(self, product_id: int) -> list[StoredSnapshot]: ...

    def add_collection_attempt(self, attempt: CollectionAttempt) -> CollectionAttempt: ...

    def add_rule(self, rule: Rule) -> Rule: ...

    def list_rules(self, product_id: int) -> list[Rule]: ...

    def get_rule(self, rule_id: int) -> Rule | None: ...

    def delete_rule(self, rule_id: int) -> None: ...

    def create_alert_event(self, event: AlertEvent) -> AlertEvent | None:
        """Persist an alert event. Returns None when idempotency_key already exists."""
        ...

    def create_alert_with_outbox(
        self,
        event: AlertEvent,
        *,
        channel: str,
        next_attempt_at: datetime,
        created_at: datetime,
    ) -> AlertEvent | None:
        """Persists the alert event and enqueues its outbox entry in a single
        transaction, so a crash (or a duplicate idempotency_key) can never
        leave one without the other. Returns None when idempotency_key
        already exists — no outbox row is created in that case either.
        """
        ...

    def get_alert_event(self, event_id: int) -> AlertEvent | None: ...

    def list_alert_events(self, product_id: int | None, limit: int) -> list[AlertEvent]: ...

    def list_outbox_for_event(self, alert_event_id: int) -> list[OutboxItem]: ...

    def enqueue_outbox(self, item: OutboxItem) -> OutboxItem: ...

    def due_outbox(self, now: datetime) -> list[OutboxItem]: ...

    def update_outbox(self, item: OutboxItem) -> OutboxItem: ...
