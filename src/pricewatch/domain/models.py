from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
    observed_at: datetime = datetime.now(timezone.utc)


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
