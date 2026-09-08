from collections.abc import Iterable

from pricewatch.collectors.base import Collector
from pricewatch.domain.models import CollectError, CollectRequest, CollectResult


class CollectorRegistry:
    def __init__(self, collectors: Iterable[Collector]) -> None:
        self._collectors = tuple(collectors)

    async def collect(self, request: CollectRequest) -> CollectResult:
        for collector in self._collectors:
            if collector.supports(request.url):
                return await collector.collect(request)

        return CollectError(
            code="unsupported",
            message="No reliable collector supports this URL yet",
            collector="registry",
            retryable=False,
        )
