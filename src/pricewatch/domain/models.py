from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        code = self.currency.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("currency must be a 3-letter alphabetic code")
        if not self.amount.is_finite():
            raise ValueError("amount must be finite")
        if self.amount < 0:
            raise ValueError("amount cannot be negative")
        object.__setattr__(self, "currency", code)


@dataclass(frozen=True, slots=True)
class OfferSnapshot:
    price: Money
    source: str
    source_kind: Literal["real", "demo"]
    price_scope: Literal["item", "item_shipping", "landed"] = "item"
    title: str | None = None
    variant_key: str | None = None
    seller: str | None = None
    availability: str | None = None
    confidence: Literal["low", "medium", "high"] = "high"
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class CollectRequest:
    url: str
    variant_key: str | None = None


@dataclass(frozen=True, slots=True)
class CollectError:
    code: str
    message: str
    collector: str
    retryable: bool = False


CollectResult = OfferSnapshot | CollectError


ProductStatus = Literal["active", "paused", "unsupported", "error", "archived"]


@dataclass(slots=True)
class Product:
    url: str
    check_interval_seconds: int
    next_check_at: datetime
    created_at: datetime
    updated_at: datetime
    id: int | None = None
    variant_key: str | None = None
    title: str | None = None
    status: ProductStatus = "active"
    consecutive_failures: int = 0


RuleKind = Literal["target_price", "absolute_drop", "percentage_drop", "new_low"]


@dataclass(slots=True)
class Rule:
    product_id: int
    kind: RuleKind
    threshold: Decimal
    created_at: datetime
    id: int | None = None
    active: bool = True


CollectionAttemptStatus = Literal["success", "error"]


@dataclass(slots=True)
class CollectionAttempt:
    product_id: int
    collector: str
    status: CollectionAttemptStatus
    observed_at: datetime
    id: int | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class AlertEvent:
    product_id: int
    rule_id: int
    idempotency_key: str
    reference_price: Decimal
    current_price: Decimal
    currency: str
    created_at: datetime
    id: int | None = None


OutboxStatus = Literal["pending", "sent", "failed"]


@dataclass(slots=True)
class OutboxItem:
    alert_event_id: int
    channel: str
    next_attempt_at: datetime
    created_at: datetime
    id: int | None = None
    status: OutboxStatus = "pending"
    attempts: int = 0
    sent_at: datetime | None = None
    last_error: str | None = None
