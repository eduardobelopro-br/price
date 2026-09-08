from decimal import Decimal
from urllib.parse import urlsplit

from pricewatch.domain.models import CollectError, CollectRequest, CollectResult, Money, OfferSnapshot


class DemoCollector:
    name = "demo"

    def supports(self, url: str) -> bool:
        parsed = urlsplit(url)
        return parsed.scheme == "https" and parsed.hostname == "demo.pricewatch.invalid"

    async def collect(self, request: CollectRequest) -> CollectResult:
        if not self.supports(request.url):
            return CollectError(
                code="unsupported",
                message="URL is not a demo URL",
                collector=self.name,
                retryable=False,
            )

        slug = urlsplit(request.url).path.strip("/") or "product"
        cents = 10000 + (sum(slug.encode("utf-8")) % 10000)
        amount = Decimal(cents) / Decimal("100")

        return OfferSnapshot(
            price=Money(amount=amount, currency="BRL"),
            source=self.name,
            source_kind="demo",
            title=f"Demo product: {slug}",
            confidence="high",
        )
