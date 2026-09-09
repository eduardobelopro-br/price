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

# A single Product node whose variants live in the offers array — the
# common real-world shape for storage-capacity/color variants.
STORAGE_VARIANTS_HTML = """
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Celular XPTO",
  "offers": [
    {"@type": "Offer", "sku": "XPTO-1TB", "price": "3000.00", "priceCurrency": "BRL"},
    {"@type": "Offer", "sku": "XPTO-2TB", "price": "3800.00", "priceCurrency": "BRL"}
  ]
}
</script>
"""

COLOR_VARIANTS_HTML = """
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Tenis Runner",
  "offers": [
    {"@type": "Offer", "color": "vermelho", "price": "299.90", "priceCurrency": "BRL"},
    {"@type": "Offer", "color": "azul", "price": "289.90", "priceCurrency": "BRL"}
  ]
}
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


def test_variant_key_not_found_among_multiple_products_is_an_error_not_a_guess() -> None:
    """The core Fase 6.2 bug: requesting a variant that matches nothing must
    never silently fall back to an unfiltered (ambiguous) candidate list.
    """
    result = extract_offer(TWO_PRODUCTS_HTML, source="generic:shop.example", variant_key="GREEN-1")

    assert isinstance(result, CollectError)
    assert result.code == "variant_not_found"


def test_sku_variants_in_a_single_products_offer_list_are_disambiguated() -> None:
    result = extract_offer(STORAGE_VARIANTS_HTML, source="generic:shop.example", variant_key="XPTO-2TB")

    assert isinstance(result, OfferSnapshot)
    assert result.price.amount == Decimal("3800.00")


def test_sku_variant_not_found_in_offer_list_is_an_error() -> None:
    result = extract_offer(STORAGE_VARIANTS_HTML, source="generic:shop.example", variant_key="XPTO-4TB")

    assert isinstance(result, CollectError)
    assert result.code == "variant_not_found"


def test_offer_list_without_variant_key_is_ambiguous() -> None:
    result = extract_offer(STORAGE_VARIANTS_HTML, source="generic:shop.example")

    assert isinstance(result, CollectError)
    assert result.code == "ambiguous_variant"


def test_color_variants_are_disambiguated() -> None:
    result = extract_offer(COLOR_VARIANTS_HTML, source="generic:shop.example", variant_key="azul")

    assert isinstance(result, OfferSnapshot)
    assert result.price.amount == Decimal("289.90")


def test_single_offer_is_accepted_even_if_variant_key_does_not_match_any_field() -> None:
    """With only one possible offer in the page there is nothing else it
    could be, so an unrelated/optimistic variant_key does not block it.
    """
    result = extract_offer(
        PRODUCT_OFFER_HTML, source="generic:shop.example", variant_key="does-not-appear-anywhere"
    )

    assert isinstance(result, OfferSnapshot)
    assert result.price.amount == Decimal("199.90")
