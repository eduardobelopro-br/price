from decimal import Decimal

from pricewatch.collectors.jsonld import extract_offer
from pricewatch.domain.models import CollectError, OfferSnapshot

PRODUCT_OFFER_HTML = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Fone Bluetooth XY",
  "offers": {
    "@type": "Offer",
    "price": "199.90",
    "priceCurrency": "BRL",
    "availability": "https://schema.org/InStock",
    "seller": {"@type": "Organization", "name": "Loja Exemplo"}
  }
}
</script>
</head><body></body></html>
"""

MISSING_CURRENCY_HTML = """
<script type="application/ld+json">
{"@type": "Product", "name": "Item", "offers": {"@type": "Offer", "price": "10.00"}}
</script>
"""

AMBIGUOUS_AGGREGATE_HTML = """
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Camiseta",
  "offers": {"@type": "AggregateOffer", "lowPrice": "39.90", "highPrice": "59.90", "priceCurrency": "BRL"}
}
</script>
"""

UNAMBIGUOUS_AGGREGATE_HTML = """
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Camiseta",
  "offers": {"@type": "AggregateOffer", "lowPrice": "39.90", "highPrice": "39.90", "priceCurrency": "BRL"}
}
</script>
"""

NO_STRUCTURED_DATA_HTML = "<html><body><p>Sem dados estruturados</p></body></html>"

TWO_PRODUCTS_HTML = """
<script type="application/ld+json">
[
  {"@type": "Product", "sku": "RED-1", "name": "Camisa vermelha",
   "offers": {"@type": "Offer", "price": "50.00", "priceCurrency": "BRL"}},
  {"@type": "Product", "sku": "BLUE-1", "name": "Camisa azul",
   "offers": {"@type": "Offer", "price": "55.00", "priceCurrency": "BRL"}}
]
</script>
"""


def test_extracts_price_and_currency_from_product_offer() -> None:
    result = extract_offer(PRODUCT_OFFER_HTML, source="generic:shop.example")

    assert isinstance(result, OfferSnapshot)
    assert result.price.amount == Decimal("199.90")
    assert result.price.currency == "BRL"
    assert result.title == "Fone Bluetooth XY"
    assert result.availability == "in_stock"
    assert result.seller == "Loja Exemplo"
    assert result.source_kind == "real"


def test_missing_currency_returns_error() -> None:
    result = extract_offer(MISSING_CURRENCY_HTML, source="generic:shop.example")

    assert isinstance(result, CollectError)
    assert result.code == "missing_currency"


def test_ambiguous_aggregate_offer_returns_error() -> None:
    result = extract_offer(AMBIGUOUS_AGGREGATE_HTML, source="generic:shop.example")

    assert isinstance(result, CollectError)
    assert result.code == "ambiguous_offer"


def test_aggregate_offer_with_single_price_is_accepted() -> None:
    result = extract_offer(UNAMBIGUOUS_AGGREGATE_HTML, source="generic:shop.example")

    assert isinstance(result, OfferSnapshot)
    assert result.price.amount == Decimal("39.90")


def test_no_structured_data_returns_unsupported() -> None:
    result = extract_offer(NO_STRUCTURED_DATA_HTML, source="generic:shop.example")

    assert isinstance(result, CollectError)
    assert result.code == "unsupported"


def test_multiple_products_without_variant_key_is_ambiguous() -> None:
    result = extract_offer(TWO_PRODUCTS_HTML, source="generic:shop.example")

    assert isinstance(result, CollectError)
    assert result.code == "ambiguous_variant"


def test_variant_key_disambiguates_multiple_products() -> None:
    result = extract_offer(TWO_PRODUCTS_HTML, source="generic:shop.example", variant_key="BLUE-1")

    assert isinstance(result, OfferSnapshot)
    assert result.price.amount == Decimal("55.00")
    assert result.variant_key == "BLUE-1"
