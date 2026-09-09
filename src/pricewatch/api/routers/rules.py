from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from pricewatch.api.deps import get_clock, get_storage, require_api_key
from pricewatch.api.schemas import RuleCreate, RuleOut
from pricewatch.clock import Clock
from pricewatch.domain.models import Rule
from pricewatch.storage.sqlite import SqliteStorage

router = APIRouter(tags=["rules"], dependencies=[Depends(require_api_key)])


def _to_out(rule: Rule) -> RuleOut:
    assert rule.id is not None
    return RuleOut(
        id=rule.id,
        product_id=rule.product_id,
        kind=rule.kind,
        threshold=rule.threshold,
        active=rule.active,
        created_at=rule.created_at,
    )


@router.post(
    "/products/{product_id}/rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED
)
async def create_rule(
    product_id: int,
    payload: RuleCreate,
    storage: SqliteStorage = Depends(get_storage),
    clock: Clock = Depends(get_clock),
) -> RuleOut:
    if storage.get_product(product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")

    rule = storage.add_rule(
        Rule(
            product_id=product_id,
            kind=payload.kind,
            threshold=payload.threshold,
            created_at=clock.now(),
        )
    )
    return _to_out(rule)


@router.get("/products/{product_id}/rules", response_model=list[RuleOut])
async def list_rules(
    product_id: int, storage: SqliteStorage = Depends(get_storage)
) -> list[RuleOut]:
    if storage.get_product(product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    return [_to_out(rule) for rule in storage.list_rules(product_id)]


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: int, storage: SqliteStorage = Depends(get_storage)) -> None:
    if storage.get_rule(rule_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rule not found")
    storage.delete_rule(rule_id)
