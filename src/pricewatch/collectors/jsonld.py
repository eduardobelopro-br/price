from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from pricewatch.domain.models import CollectError, Money, OfferSnapshot

_SCRIPT_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

_AVAILABILITY_MAP = {
    "https://schema.org/InStock": "in_stock",
    "http://schema.org/InStock": "in_stock",
    "https://schema.org/OutOfStock": "out_of_stock",
    "http://schema.org/OutOfStock": "out_of_stock",
    "https://schema.org/PreOrder": "preorder",
    "http://schema.org/PreOrder": "preorder",
    "https://schema.org/LimitedAvailability": "limited",
    "http://schema.org/LimitedAvailability": "limited",
}


def _iter_json_ld_blocks(html: str) -> list[Any]:
    blocks: list[Any] = []
    for match in _SCRIPT_RE.finditer(html):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            blocks.append(json.loads(raw, parse_float=Decimal))
        except json.JSONDecodeError:
            continue
    return blocks


def _iter_nodes(data: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            nodes.extend(_iter_nodes(item))
    elif isinstance(data, dict):
        if "@graph" in data:
            nodes.extend(_iter_nodes(data["@graph"]))
        else:
            nodes.append(data)
    return nodes


def _type_matches(node: dict[str, Any], name: str) -> bool:
    node_type = node.get("@type")
    types = node_type if isinstance(node_type, list) else [node_type]
    return any(t == name for t in types if isinstance(t, str))


def _find_products(html: str) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for block in _iter_json_ld_blocks(html):
        for node in _iter_nodes(block):
            if _type_matches(node, "Product"):
                products.append(node)
    return products


def _extract_price_and_currency(offer: dict[str, Any]) -> tuple[Decimal, str] | CollectError:
    offer_type = offer.get("@type")
    types = offer_type if isinstance(offer_type, list) else [offer_type]
    is_aggregate = any(t == "AggregateOffer" for t in types if isinstance(t, str))

    if is_aggregate:
        low, high = offer.get("lowPrice"), offer.get("highPrice")
        if low is None or high is None:
            return CollectError(
                code="ambiguous_offer",
                message="AggregateOffer without lowPrice/highPrice cannot be represented safely",
                collector="generic",
            )
        try:
            if Decimal(str(low)) != Decimal(str(high)):
                return CollectError(
                    code="ambiguous_offer",
                    message="AggregateOffer spans a price range and cannot be "
                    "represented as a single offer",
                    collector="generic",
                )
        except InvalidOperation:
            return CollectError(
                code="invalid_price", message="invalid AggregateOffer price", collector="generic"
            )
        raw_price = low
    else:
        raw_price = offer.get("price")
        if raw_price is None:
            return CollectError(code="missing_price", message="offer has no price", collector="generic")

    currency = offer.get("priceCurrency")
    if not currency:
        return CollectError(
            code="missing_currency", message="offer has no priceCurrency", collector="generic"
        )

    try:
        amount = Decimal(str(raw_price))
    except InvalidOperation:
        return CollectError(
            code="invalid_price",
            message=f"price is not a valid number: {raw_price!r}",
            collector="generic",
        )

    return amount, str(currency)


def _select_offer(product: dict[str, Any]) -> dict[str, Any] | CollectError:
    offer = product.get("offers")
    if isinstance(offer, list):
        if len(offer) != 1:
            return CollectError(
                code="ambiguous_offer",
                message="multiple offers found for product",
                collector="generic",
            )
        offer = offer[0]
    if not isinstance(offer, dict):
        return CollectError(code="missing_price", message="product has no offer", collector="generic")
    return offer


def extract_offer(
    html: str, *, source: str, variant_key: str | None = None
) -> OfferSnapshot | CollectError:
    products = _find_products(html)
    if not products:
        return CollectError(
            code="unsupported", message="no Product structured data found", collector="generic"
        )

    candidates = products
    if variant_key:
        filtered = [
            product
            for product in products
            if variant_key.lower() in json.dumps(product, default=str).lower()
        ]
        if filtered:
            candidates = filtered

    if len(candidates) > 1:
        return CollectError(
            code="ambiguous_variant",
            message="multiple products found; specify variant_key to disambiguate",
            collector="generic",
        )

    product = candidates[0]
    offer = _select_offer(product)
    if isinstance(offer, CollectError):
        return offer

    result = _extract_price_and_currency(offer)
    if isinstance(result, CollectError):
        return result
    amount, currency = result

    try:
        price = Money(amount, currency)
    except ValueError as exc:
        return CollectError(code="invalid_price", message=str(exc), collector="generic")

    availability_raw = offer.get("availability")
    availability = _AVAILABILITY_MAP.get(availability_raw) if isinstance(availability_raw, str) else None

    seller = offer.get("seller")
    seller_name = seller.get("name") if isinstance(seller, dict) else None
    title = product.get("name")

    return OfferSnapshot(
        price=price,
        source=source,
        source_kind="real",
        title=title if isinstance(title, str) else None,
        variant_key=variant_key,
        seller=seller_name if isinstance(seller_name, str) else None,
        availability=availability,
        confidence="medium",
    )
