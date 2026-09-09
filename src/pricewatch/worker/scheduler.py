from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlsplit

from pricewatch.clock import Clock
from pricewatch.domain.models import CollectError, Product
from pricewatch.services.monitor import MonitorService
from pricewatch.storage.base import Storage

logger = logging.getLogger(__name__)


class Worker:
    """Selects due products and checks them concurrently, bounded globally
    and per domain so one slow/misbehaving store cannot starve the others.
    A product whose check raises an unexpected exception is isolated: it is
    logged, recorded as a retryable collection failure, and does not bring
    down the batch.
    """

    def __init__(
        self,
        storage: Storage,
        monitor: MonitorService,
        clock: Clock,
        *,
        max_concurrency: int = 5,
        max_concurrency_per_domain: int = 1,
    ) -> None:
        self._storage = storage
        self._monitor = monitor
        self._clock = clock
        self._global_semaphore = asyncio.Semaphore(max_concurrency)
        self._max_concurrency_per_domain = max_concurrency_per_domain
        self._domain_semaphores: dict[str, asyncio.Semaphore] = {}

    async def run_once(self) -> int:
        due = self._storage.due_products(self._clock.now())
        if not due:
            return 0

        await asyncio.gather(*(self._process(product) for product in due))
        return len(due)

    async def _process(self, product: Product) -> None:
        async with self._global_semaphore, self._domain_semaphore(product.url):
            try:
                await self._monitor.check(product)
            except Exception as exc:
                logger.exception(
                    "unexpected error while checking product",
                    extra={"product_id": product.id, "domain": urlsplit(product.url).hostname},
                )
                self._monitor.record_failure(
                    product,
                    CollectError(
                        code="internal_error",
                        message=str(exc),
                        collector="worker",
                        retryable=True,
                    ),
                )

    def _domain_semaphore(self, url: str) -> asyncio.Semaphore:
        domain = urlsplit(url).hostname or "unknown"
        semaphore = self._domain_semaphores.get(domain)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self._max_concurrency_per_domain)
            self._domain_semaphores[domain] = semaphore
        return semaphore
