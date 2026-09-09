from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Self

from pricewatch.domain.models import (
    AlertEvent,
    CollectionAttempt,
    Money,
    OfferSnapshot,
    OutboxItem,
    Product,
    Rule,
    StoredSnapshot,
)
from pricewatch.storage.migrator import apply_migrations


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _dump_dt(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


class SqliteStorage:
    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        # ASGI servers (and TestClient) may dispatch requests on a worker
        # thread different from the one that opened this connection.
        self._connection = sqlite3.connect(self._path, check_same_thread=False)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.row_factory = sqlite3.Row
        apply_migrations(self._connection)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- products ---------------------------------------------------

    def create_product(self, product: Product) -> Product:
        cursor = self._connection.execute(
            """
            INSERT INTO products (
                url, variant_key, title, status, check_interval_seconds,
                next_check_at, created_at, updated_at, consecutive_failures
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product.url,
                product.variant_key,
                product.title,
                product.status,
                product.check_interval_seconds,
                _dump_dt(product.next_check_at),
                _dump_dt(product.created_at),
                _dump_dt(product.updated_at),
                product.consecutive_failures,
            ),
        )
        self._connection.commit()
        assert cursor.lastrowid is not None
        created = self.get_product(cursor.lastrowid)
        assert created is not None
        return created

    def get_product(self, product_id: int) -> Product | None:
        row = self._connection.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        return self._row_to_product(row) if row else None

    def get_product_by_url(self, url: str) -> Product | None:
        row = self._connection.execute(
            "SELECT * FROM products WHERE url = ?", (url,)
        ).fetchone()
        return self._row_to_product(row) if row else None

    def list_products(self) -> list[Product]:
        rows = self._connection.execute("SELECT * FROM products ORDER BY id").fetchall()
        return [self._row_to_product(row) for row in rows]

    def update_product(self, product: Product) -> Product:
        if product.id is None:
            raise ValueError("cannot update a product without id")
        self._connection.execute(
            """
            UPDATE products
            SET url = ?, variant_key = ?, title = ?, status = ?,
                check_interval_seconds = ?, next_check_at = ?, updated_at = ?,
                consecutive_failures = ?
            WHERE id = ?
            """,
            (
                product.url,
                product.variant_key,
                product.title,
                product.status,
                product.check_interval_seconds,
                _dump_dt(product.next_check_at),
                _dump_dt(product.updated_at),
                product.consecutive_failures,
                product.id,
            ),
        )
        self._connection.commit()
        updated = self.get_product(product.id)
        assert updated is not None
        return updated

    def due_products(self, now: datetime) -> list[Product]:
        rows = self._connection.execute(
            "SELECT * FROM products WHERE status = 'active' AND next_check_at <= ? ORDER BY next_check_at",
            (_dump_dt(now),),
        ).fetchall()
        return [self._row_to_product(row) for row in rows]

    @staticmethod
    def _row_to_product(row: sqlite3.Row) -> Product:
        return Product(
            id=row["id"],
            url=row["url"],
            variant_key=row["variant_key"],
            title=row["title"],
            status=row["status"],
            check_interval_seconds=row["check_interval_seconds"],
            next_check_at=_parse_dt(row["next_check_at"]),
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            consecutive_failures=row["consecutive_failures"],
        )

    # -- snapshots ----------------------------------------------------

    def add_snapshot(self, product_id: int, snapshot: OfferSnapshot) -> StoredSnapshot:
        cursor = self._connection.execute(
            """
            INSERT INTO snapshots (
                product_id, amount, currency, source, source_kind, price_scope,
                title, variant_key, seller, availability, confidence, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                str(snapshot.price.amount),
                snapshot.price.currency,
                snapshot.source,
                snapshot.source_kind,
                snapshot.price_scope,
                snapshot.title,
                snapshot.variant_key,
                snapshot.seller,
                snapshot.availability,
                snapshot.confidence,
                _dump_dt(snapshot.observed_at),
            ),
        )
        self._connection.commit()
        assert cursor.lastrowid is not None
        return StoredSnapshot(id=cursor.lastrowid, product_id=product_id, offer=snapshot)

    def last_snapshot(self, product_id: int) -> StoredSnapshot | None:
        row = self._connection.execute(
            "SELECT * FROM snapshots WHERE product_id = ? ORDER BY observed_at DESC, id DESC LIMIT 1",
            (product_id,),
        ).fetchone()
        return self._row_to_stored_snapshot(row) if row else None

    def list_snapshots(self, product_id: int) -> list[StoredSnapshot]:
        rows = self._connection.execute(
            "SELECT * FROM snapshots WHERE product_id = ? ORDER BY observed_at",
            (product_id,),
        ).fetchall()
        return [self._row_to_stored_snapshot(row) for row in rows]

    @staticmethod
    def _row_to_stored_snapshot(row: sqlite3.Row) -> StoredSnapshot:
        return StoredSnapshot(
            id=row["id"],
            product_id=row["product_id"],
            offer=OfferSnapshot(
                price=Money(Decimal(row["amount"]), row["currency"]),
                source=row["source"],
                source_kind=row["source_kind"],
                price_scope=row["price_scope"],
                title=row["title"],
                variant_key=row["variant_key"],
                seller=row["seller"],
                availability=row["availability"],
                confidence=row["confidence"],
                observed_at=_parse_dt(row["observed_at"]),
            ),
        )

    # -- collection attempts ------------------------------------------

    def add_collection_attempt(self, attempt: CollectionAttempt) -> CollectionAttempt:
        cursor = self._connection.execute(
            """
            INSERT INTO collection_attempts (
                product_id, collector, status, error_code, error_message, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                attempt.product_id,
                attempt.collector,
                attempt.status,
                attempt.error_code,
                attempt.error_message,
                _dump_dt(attempt.observed_at),
            ),
        )
        self._connection.commit()
        return CollectionAttempt(
            id=cursor.lastrowid,
            product_id=attempt.product_id,
            collector=attempt.collector,
            status=attempt.status,
            error_code=attempt.error_code,
            error_message=attempt.error_message,
            observed_at=attempt.observed_at,
        )

    def list_collection_attempts(self, product_id: int) -> list[CollectionAttempt]:
        rows = self._connection.execute(
            "SELECT * FROM collection_attempts WHERE product_id = ? ORDER BY observed_at",
            (product_id,),
        ).fetchall()
        return [
            CollectionAttempt(
                id=row["id"],
                product_id=row["product_id"],
                collector=row["collector"],
                status=row["status"],
                error_code=row["error_code"],
                error_message=row["error_message"],
                observed_at=_parse_dt(row["observed_at"]),
            )
            for row in rows
        ]

    # -- rules ---------------------------------------------------------

    def add_rule(self, rule: Rule) -> Rule:
        cursor = self._connection.execute(
            """
            INSERT INTO rules (product_id, kind, threshold, active, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                rule.product_id,
                rule.kind,
                str(rule.threshold),
                1 if rule.active else 0,
                _dump_dt(rule.created_at),
            ),
        )
        self._connection.commit()
        return Rule(
            id=cursor.lastrowid,
            product_id=rule.product_id,
            kind=rule.kind,
            threshold=rule.threshold,
            active=rule.active,
            created_at=rule.created_at,
        )

    def list_rules(self, product_id: int) -> list[Rule]:
        rows = self._connection.execute(
            "SELECT * FROM rules WHERE product_id = ? ORDER BY id", (product_id,)
        ).fetchall()
        return [self._row_to_rule(row) for row in rows]

    def get_rule(self, rule_id: int) -> Rule | None:
        row = self._connection.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
        return self._row_to_rule(row) if row else None

    def delete_rule(self, rule_id: int) -> None:
        self._connection.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        self._connection.commit()

    @staticmethod
    def _row_to_rule(row: sqlite3.Row) -> Rule:
        return Rule(
            id=row["id"],
            product_id=row["product_id"],
            kind=row["kind"],
            threshold=Decimal(row["threshold"]),
            active=bool(row["active"]),
            created_at=_parse_dt(row["created_at"]),
        )

    # -- alert events ----------------------------------------------------

    def create_alert_event(self, event: AlertEvent) -> AlertEvent | None:
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO alert_events (
                    product_id, rule_id, idempotency_key, reference_price,
                    current_price, currency, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.product_id,
                    event.rule_id,
                    event.idempotency_key,
                    str(event.reference_price),
                    str(event.current_price),
                    event.currency,
                    _dump_dt(event.created_at),
                ),
            )
        except sqlite3.IntegrityError:
            self._connection.rollback()
            return None

        self._connection.commit()
        return AlertEvent(
            id=cursor.lastrowid,
            product_id=event.product_id,
            rule_id=event.rule_id,
            idempotency_key=event.idempotency_key,
            reference_price=event.reference_price,
            current_price=event.current_price,
            currency=event.currency,
            created_at=event.created_at,
        )

    def create_alert_with_outbox(
        self,
        event: AlertEvent,
        *,
        channel: str,
        next_attempt_at: datetime,
        created_at: datetime,
    ) -> AlertEvent | None:
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            cursor = self._connection.execute(
                """
                INSERT INTO alert_events (
                    product_id, rule_id, idempotency_key, reference_price,
                    current_price, currency, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.product_id,
                    event.rule_id,
                    event.idempotency_key,
                    str(event.reference_price),
                    str(event.current_price),
                    event.currency,
                    _dump_dt(event.created_at),
                ),
            )
            event_id = cursor.lastrowid
            assert event_id is not None
            self._connection.execute(
                """
                INSERT INTO outbox (
                    alert_event_id, channel, status, attempts, next_attempt_at,
                    created_at, sent_at, last_error
                ) VALUES (?, ?, 'pending', 0, ?, ?, NULL, NULL)
                """,
                (event_id, channel, _dump_dt(next_attempt_at), _dump_dt(created_at)),
            )
        except sqlite3.IntegrityError:
            self._connection.rollback()
            return None

        self._connection.commit()
        return AlertEvent(
            id=event_id,
            product_id=event.product_id,
            rule_id=event.rule_id,
            idempotency_key=event.idempotency_key,
            reference_price=event.reference_price,
            current_price=event.current_price,
            currency=event.currency,
            created_at=event.created_at,
        )

    def get_alert_event_by_key(self, idempotency_key: str) -> AlertEvent | None:
        row = self._connection.execute(
            "SELECT * FROM alert_events WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        return self._row_to_alert_event(row) if row else None

    def get_alert_event(self, event_id: int) -> AlertEvent | None:
        row = self._connection.execute(
            "SELECT * FROM alert_events WHERE id = ?", (event_id,)
        ).fetchone()
        return self._row_to_alert_event(row) if row else None

    @staticmethod
    def _row_to_alert_event(row: sqlite3.Row) -> AlertEvent:
        return AlertEvent(
            id=row["id"],
            product_id=row["product_id"],
            rule_id=row["rule_id"],
            idempotency_key=row["idempotency_key"],
            reference_price=Decimal(row["reference_price"]),
            current_price=Decimal(row["current_price"]),
            currency=row["currency"],
            created_at=_parse_dt(row["created_at"]),
        )

    def list_alert_events(self, product_id: int | None, limit: int) -> list[AlertEvent]:
        if product_id is None:
            rows = self._connection.execute(
                "SELECT * FROM alert_events ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM alert_events WHERE product_id = ? ORDER BY created_at DESC LIMIT ?",
                (product_id, limit),
            ).fetchall()
        return [self._row_to_alert_event(row) for row in rows]

    def list_outbox_for_event(self, alert_event_id: int) -> list[OutboxItem]:
        rows = self._connection.execute(
            "SELECT * FROM outbox WHERE alert_event_id = ? ORDER BY id", (alert_event_id,)
        ).fetchall()
        return [self._row_to_outbox(row) for row in rows]

    # -- outbox ----------------------------------------------------------

    def enqueue_outbox(self, item: OutboxItem) -> OutboxItem:
        cursor = self._connection.execute(
            """
            INSERT INTO outbox (
                alert_event_id, channel, status, attempts, next_attempt_at,
                created_at, sent_at, last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.alert_event_id,
                item.channel,
                item.status,
                item.attempts,
                _dump_dt(item.next_attempt_at),
                _dump_dt(item.created_at),
                _dump_dt(item.sent_at) if item.sent_at else None,
                item.last_error,
            ),
        )
        self._connection.commit()
        assert cursor.lastrowid is not None
        return self._get_outbox(cursor.lastrowid)

    def due_outbox(self, now: datetime) -> list[OutboxItem]:
        rows = self._connection.execute(
            "SELECT * FROM outbox WHERE status = 'pending' AND next_attempt_at <= ? ORDER BY next_attempt_at",
            (_dump_dt(now),),
        ).fetchall()
        return [self._row_to_outbox(row) for row in rows]

    def update_outbox(self, item: OutboxItem) -> OutboxItem:
        if item.id is None:
            raise ValueError("cannot update an outbox item without id")
        self._connection.execute(
            """
            UPDATE outbox
            SET status = ?, attempts = ?, next_attempt_at = ?, sent_at = ?, last_error = ?
            WHERE id = ?
            """,
            (
                item.status,
                item.attempts,
                _dump_dt(item.next_attempt_at),
                _dump_dt(item.sent_at) if item.sent_at else None,
                item.last_error,
                item.id,
            ),
        )
        self._connection.commit()
        return self._get_outbox(item.id)

    def _get_outbox(self, outbox_id: int) -> OutboxItem:
        row = self._connection.execute(
            "SELECT * FROM outbox WHERE id = ?", (outbox_id,)
        ).fetchone()
        return self._row_to_outbox(row)

    @staticmethod
    def _row_to_outbox(row: sqlite3.Row) -> OutboxItem:
        return OutboxItem(
            id=row["id"],
            alert_event_id=row["alert_event_id"],
            channel=row["channel"],
            status=row["status"],
            attempts=row["attempts"],
            next_attempt_at=_parse_dt(row["next_attempt_at"]),
            created_at=_parse_dt(row["created_at"]),
            sent_at=_parse_dt(row["sent_at"]) if row["sent_at"] else None,
            last_error=row["last_error"],
        )
