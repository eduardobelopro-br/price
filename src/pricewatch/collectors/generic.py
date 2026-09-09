from __future__ import annotations

from urllib.parse import urlsplit

from pricewatch.collectors.jsonld import extract_offer
from pricewatch.domain.models import CollectError, CollectRequest, CollectResult
from pricewatch.net.http_client import FetchError, SecureHttpClient
from pricewatch.net.url_safety import UrlSafetyError


class GenericStructuredDataCollector:
    """Collects offers from structured data (JSON-LD Product/Offer) that the
    page itself publishes. Does not scrape arbitrary HTML.
    """

    name = "generic"

    def __init__(self, http_client: SecureHttpClient) -> None:
        self._http_client = http_client

    def supports(self, url: str) -> bool:
        return urlsplit(url).scheme in ("http", "https")

    async def collect(self, request: CollectRequest) -> CollectResult:
        try:
            result = await self._http_client.fetch(request.url)
        except UrlSafetyError as exc:
            return CollectError(code="blocked_url", message=str(exc), collector=self.name, retryable=False)
        except FetchError as exc:
            return CollectError(code="fetch_failed", message=str(exc), collector=self.name, retryable=True)

        if result.status_code >= 400:
            return CollectError(
                code="http_error",
                message=f"unexpected status code {result.status_code}",
                collector=self.name,
                retryable=result.status_code >= 500,
            )

        html = result.body.decode("utf-8", errors="replace")
        hostname = urlsplit(request.url).hostname or self.name
        return extract_offer(html, source=f"{self.name}:{hostname}", variant_key=request.variant_key)
