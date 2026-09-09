from __future__ import annotations

import logging
from datetime import datetime, timedelta

from pricewatch.clock import Clock
from pricewatch.domain.models import OutboxItem
from pricewatch.notifications.telegram import (
    NotificationError,
    TelegramNotifier,
    format_alert_message,
)
from pricewatch.storage.base import Storage

logger = logging.getLogger(__name__)


class OutboxDispatcher:
    """Delivers pending outbox items. Delivery is re-triggerable: a crash
    between sending and marking the item as sent simply means the item is
    retried, and downstream de-duplication is Telegram/channel-specific
    (out of scope for the MVP outbox itself).
    """

    def __init__(
        self,
        storage: Storage,
        notifier: TelegramNotifier,
        clock: Clock,
        *,
        max_attempts: int = 5,
        retry_backoff_seconds: int = 60,
    ) -> None:
        self._storage = storage
        self._notifier = notifier
        self._clock = clock
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    async def dispatch_due(self) -> int:
        now = self._clock.now()
        due = self._storage.due_outbox(now)
        for item in due:
            await self._dispatch_one(item, now)
        return len(due)

    async def _dispatch_one(self, item: OutboxItem, now: datetime) -> None:
        event = self._storage.get_alert_event(item.alert_event_id)
        if event is None:
            self._fail_permanently(item, "alert event not found")
            return

        product = self._storage.get_product(event.product_id)
        rule = self._storage.get_rule(event.rule_id)
        if product is None or rule is None:
            self._fail_permanently(item, "product or rule not found")
            return

        try:
            await self._notifier.send(format_alert_message(product, rule, event))
        except NotificationError as exc:
            self._retry_or_fail(item, now, str(exc))
            return

        item.status = "sent"
        item.sent_at = now
        item.attempts += 1
        self._storage.update_outbox(item)

    def _retry_or_fail(self, item: OutboxItem, now: datetime, error: str) -> None:
        item.attempts += 1
        item.last_error = error
        if item.attempts >= self._max_attempts:
            item.status = "failed"
        else:
            item.next_attempt_at = now + timedelta(
                seconds=self._retry_backoff_seconds * item.attempts
            )
        self._storage.update_outbox(item)
        logger.warning(
            "notification delivery failed",
            extra={
                "alert_event_id": item.alert_event_id,
                "channel": item.channel,
                "attempt": item.attempts,
                "max_attempts": self._max_attempts,
                "error": error,
            },
        )

    def _fail_permanently(self, item: OutboxItem, error: str) -> None:
        item.status = "failed"
        item.last_error = error
        self._storage.update_outbox(item)
        logger.error(
            "notification permanently failed",
            extra={"alert_event_id": item.alert_event_id, "channel": item.channel, "error": error},
        )
