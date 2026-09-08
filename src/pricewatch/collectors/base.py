from typing import Protocol

from pricewatch.domain.models import CollectRequest, CollectResult


class Collector(Protocol):
    name: str

    def supports(self, url: str) -> bool: ...

    async def collect(self, request: CollectRequest) -> CollectResult: ...
