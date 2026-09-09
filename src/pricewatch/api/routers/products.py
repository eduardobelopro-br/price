from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from pricewatch.api.deps import get_clock, get_monitor, get_settings, get_storage, require_api_key
from pricewatch.api.schemas import (
    ProductCreate,
    ProductDetailOut,
    ProductOut,
    ProductUpdate,
    RecentErrorOut,
    SnapshotOut,
)
from pricewatch.clock import Clock
from pricewatch.domain.models import Product
from pricewatch.net.url_safety import UrlSafetyError, validate_scheme_and_credentials
from pricewatch.services.monitor import MonitorService
from pricewatch.settings import Settings
from pricewatch.storage.sqlite import SqliteStorage

router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(require_api_key)])

MIN_MANUAL_CHECK_INTERVAL_SECONDS = 10
MAX_RECENT_ERRORS = 5


def _to_out(storage: SqliteStorage, product: Product) -> ProductOut:
    assert product.id is not None
    last = storage.last_snapshot(product.id)
    return ProductOut(
        id=product.id,
        url=product.url,
        variant_key=product.variant_key,
        title=product.title,
        status=product.status,
        check_interval_seconds=product.check_interval_seconds,
        next_check_at=product.next_check_at,
        consecutive_failures=product.consecutive_failures,
        created_at=product.created_at,
        updated_at=product.updated_at,
        last_price_amount=last.offer.price.amount if last else None,
        last_price_currency=last.offer.price.currency if last else None,
        last_checked_at=last.offer.observed_at if last else None,
    )


def _get_or_404(storage: SqliteStorage, product_id: int) -> Product:
    product = storage.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    return product


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    storage: SqliteStorage = Depends(get_storage),
    clock: Clock = Depends(get_clock),
    settings: Settings = Depends(get_settings),
) -> ProductOut:
    try:
        validate_scheme_and_credentials(payload.url)
    except UrlSafetyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    if storage.get_product_by_url(payload.url) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="product with this URL already exists"
        )

    now = clock.now()
    product = storage.create_product(
        Product(
            url=payload.url,
            variant_key=payload.variant_key,
            title=payload.title,
            check_interval_seconds=payload.check_interval_seconds
            or settings.default_check_interval_seconds,
            next_check_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    return _to_out(storage, product)


@router.get("", response_model=list[ProductOut])
async def list_products(storage: SqliteStorage = Depends(get_storage)) -> list[ProductOut]:
    return [_to_out(storage, product) for product in storage.list_products()]


@router.get("/{product_id}", response_model=ProductDetailOut)
async def get_product(
    product_id: int, storage: SqliteStorage = Depends(get_storage)
) -> ProductDetailOut:
    product = _get_or_404(storage, product_id)
    base = _to_out(storage, product)
    errors = [
        RecentErrorOut(
            observed_at=attempt.observed_at,
            collector=attempt.collector,
            error_code=attempt.error_code,
            error_message=attempt.error_message,
        )
        for attempt in storage.list_collection_attempts(product_id)
        if attempt.status == "error"
    ]
    return ProductDetailOut(**base.model_dump(), recent_errors=list(reversed(errors[-MAX_RECENT_ERRORS:])))


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    storage: SqliteStorage = Depends(get_storage),
    clock: Clock = Depends(get_clock),
) -> ProductOut:
    product = _get_or_404(storage, product_id)
    if payload.status is not None:
        product.status = payload.status
    if payload.check_interval_seconds is not None:
        product.check_interval_seconds = payload.check_interval_seconds
    if payload.title is not None:
        product.title = payload.title
    if payload.variant_key is not None:
        product.variant_key = payload.variant_key
    product.updated_at = clock.now()
    updated = storage.update_product(product)
    return _to_out(storage, updated)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_product(
    product_id: int,
    storage: SqliteStorage = Depends(get_storage),
    clock: Clock = Depends(get_clock),
) -> None:
    product = _get_or_404(storage, product_id)
    product.status = "archived"
    product.updated_at = clock.now()
    storage.update_product(product)


@router.post("/{product_id}/check", response_model=ProductOut)
async def check_product_now(
    product_id: int,
    storage: SqliteStorage = Depends(get_storage),
    monitor: MonitorService = Depends(get_monitor),
    clock: Clock = Depends(get_clock),
) -> ProductOut:
    product = _get_or_404(storage, product_id)
    now = clock.now()
    attempts = storage.list_collection_attempts(product_id)
    if attempts and now - attempts[-1].observed_at < timedelta(
        seconds=MIN_MANUAL_CHECK_INTERVAL_SECONDS
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="checked too recently, try again shortly",
        )

    outcome = await monitor.check(product)
    return _to_out(storage, outcome.product)


@router.get("/{product_id}/history", response_model=list[SnapshotOut])
async def get_history(
    product_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    storage: SqliteStorage = Depends(get_storage),
) -> list[SnapshotOut]:
    _get_or_404(storage, product_id)
    stored_snapshots = sorted(
        storage.list_snapshots(product_id), key=lambda s: s.offer.observed_at, reverse=True
    )
    return [
        SnapshotOut(
            price_amount=stored.offer.price.amount,
            price_currency=stored.offer.price.currency,
            source=stored.offer.source,
            source_kind=stored.offer.source_kind,
            price_scope=stored.offer.price_scope,
            title=stored.offer.title,
            variant_key=stored.offer.variant_key,
            seller=stored.offer.seller,
            availability=stored.offer.availability,
            confidence=stored.offer.confidence,
            observed_at=stored.offer.observed_at,
        )
        for stored in stored_snapshots[:limit]
    ]
