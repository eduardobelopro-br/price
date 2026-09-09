from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from pricewatch.api.deps import get_storage, require_api_key
from pricewatch.api.schemas import AlertOut, OutboxStatusOut
from pricewatch.storage.sqlite import SqliteStorage

router = APIRouter(tags=["alerts"], dependencies=[Depends(require_api_key)])


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    product_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    storage: SqliteStorage = Depends(get_storage),
) -> list[AlertOut]:
    out: list[AlertOut] = []
    for event in storage.list_alert_events(product_id=product_id, limit=limit):
        assert event.id is not None
        deliveries = [
            OutboxStatusOut(
                channel=item.channel,
                status=item.status,
                attempts=item.attempts,
                last_error=item.last_error,
            )
            for item in storage.list_outbox_for_event(event.id)
        ]
        out.append(
            AlertOut(
                id=event.id,
                product_id=event.product_id,
                rule_id=event.rule_id,
                reference_price=event.reference_price,
                current_price=event.current_price,
                currency=event.currency,
                created_at=event.created_at,
                deliveries=deliveries,
            )
        )
    return out
