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


# Fields that identify a specific variant/listing. Checked on both the
# Product node and the Offer node, since real-world JSON-LD puts the SKU
# on either one depending on the site.
_VARIANT_IDENTIFIER_FIELDS = (
    "sku",
    "mpn",
    "gtin",
    "gtin8",
    "gtin12",
    "gtin13",
    "gtin14",
    "model",
    "color",
    "size",
    "name",
)


def _identifier_values(node: dict[str, Any]) -> list[str]:
    values = []
    for field in _VARIANT_IDENTIFIER_FIELDS:
        value = node.get(field)
        if isinstance(value, str) and value:
            values.append(value.lower())
    return values


def _matches_variant_key(node: dict[str, Any], variant_key: str) -> bool:
    needle = variant_key.lower()
    return any(needle == value or needle in value for value in _identifier_values(node))


def _collect_leaf_offers(products: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Flattens every product's offer(s) into (product, offer) pairs — one
    per entry when `offers` is a list, since that is how most real sites
    represent per-variant (per-SKU/color/size) pricing under a single
    Product node.
    """
    leaves: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for product in products:
        offer = product.get("offers")
        if isinstance(offer, list):
            leaves.extend((product, entry) for entry in offer if isinstance(entry, dict))
        elif isinstance(offer, dict):
            leaves.append((product, offer))
    return leaves


def _select_candidate(
    leaves: list[tuple[dict[str, Any], dict[str, Any]]], variant_key: str | None
) -> tuple[dict[str, Any], dict[str, Any]] | CollectError:
    if not variant_key:
        if len(leaves) > 1:
            return CollectError(
                code="ambiguous_variant",
                message="multiple offers found; specify variant_key to disambiguate",
                collector="generic",
            )
        return leaves[0]

    matches = [
        (product, offer)
        for product, offer in leaves
        if _matches_variant_key(product, variant_key) or _matches_variant_key(offer, variant_key)
    ]

    if not matches:
        # With only one possible offer in the page, there is nothing else it
        # could be, so it is safe to accept it. With more than one, we have
        # no evidence which one matches — fail rather than guess.
        if len(leaves) == 1:
            return leaves[0]
        return CollectError(
            code="variant_not_found",
            message=f"requested variant {variant_key!r} was not found in structured product data",
            collector="generic",
            retryable=False,
        )

    if len(matches) > 1:
        return CollectError(
            code="ambiguous_variant",
            message=f"multiple offers match the requested variant {variant_key!r}",
            collector="generic",
        )

    return matches[0]


def extract_offer(
    html: str, *, source: str, variant_key: str | None = None
) -> OfferSnapshot | CollectError:
    products = _find_products(html)
    if not products:
        return CollectError(
            code="unsupported", message="no Product structured data found", collector="generic"
        )

    leaves = _collect_leaf_offers(products)
    if not leaves:
        return CollectError(
            code="missing_price", message="no offer found in structured product data", collector="generic"
        )

    candidate = _select_candidate(leaves, variant_key)
    if isinstance(candidate, CollectError):
        return candidate
    product, offer = candidate

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
