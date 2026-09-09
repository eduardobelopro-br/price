from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from pricewatch.domain.models import ProductStatus, RuleKind


class ProductCreate(BaseModel):
    url: str
    variant_key: str | None = None
    title: str | None = None
    check_interval_seconds: int | None = Field(default=None, gt=0)


class ProductUpdate(BaseModel):
    status: ProductStatus | None = None
    check_interval_seconds: int | None = Field(default=None, gt=0)
    title: str | None = None
    variant_key: str | None = None


class ProductOut(BaseModel):
    id: int
    url: str
    variant_key: str | None
    title: str | None
    status: ProductStatus
    check_interval_seconds: int
    next_check_at: datetime
    consecutive_failures: int
    created_at: datetime
    updated_at: datetime
    last_price_amount: Decimal | None = None
    last_price_currency: str | None = None
    last_checked_at: datetime | None = None


class RecentErrorOut(BaseModel):
    observed_at: datetime
    collector: str
    error_code: str | None
    error_message: str | None


class ProductDetailOut(ProductOut):
    recent_errors: list[RecentErrorOut] = Field(default_factory=list)


class SnapshotOut(BaseModel):
    price_amount: Decimal
    price_currency: str
    source: str
    source_kind: str
    price_scope: str
    title: str | None
    variant_key: str | None
    seller: str | None
    availability: str | None
    confidence: str
    observed_at: datetime


class RuleCreate(BaseModel):
    kind: RuleKind
    threshold: Decimal


class RuleOut(BaseModel):
    id: int
    product_id: int
    kind: RuleKind
    threshold: Decimal
    active: bool
    created_at: datetime


class OutboxStatusOut(BaseModel):
    channel: str
    status: str
    attempts: int
    last_error: str | None


class AlertOut(BaseModel):
    id: int
    product_id: int
    rule_id: int
    reference_price: Decimal
    current_price: Decimal
    currency: str
    created_at: datetime
    deliveries: list[OutboxStatusOut] = Field(default_factory=list)
