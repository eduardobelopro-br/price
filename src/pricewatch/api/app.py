from decimal import Decimal

from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl

from pricewatch.collectors.demo import DemoCollector
from pricewatch.collectors.registry import CollectorRegistry
from pricewatch.domain.models import CollectError, CollectRequest, OfferSnapshot

app = FastAPI(title="Price", version="0.1.0")
registry = CollectorRegistry([DemoCollector()])


class DemoCollectIn(BaseModel):
    url: HttpUrl


class CollectOut(BaseModel):
    ok: bool
    title: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    source: str
    source_kind: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/demo-collect", response_model=CollectOut)
async def demo_collect(payload: DemoCollectIn) -> CollectOut:
    result = await registry.collect(CollectRequest(url=str(payload.url)))

    if isinstance(result, CollectError):
        return CollectOut(
            ok=False,
            source=result.collector,
            error_code=result.code,
            error_message=result.message,
        )

    assert isinstance(result, OfferSnapshot)
    return CollectOut(
        ok=True,
        title=result.title,
        amount=result.price.amount,
        currency=result.price.currency,
        source=result.source,
        source_kind=result.source_kind,
    )
