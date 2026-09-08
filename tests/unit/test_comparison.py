from decimal import Decimal

from pricewatch.domain.models import Money, OfferSnapshot
from pricewatch.services.comparison import comparable


def snap(currency: str, variant: str | None = None) -> OfferSnapshot:
    return OfferSnapshot(
        price=Money(Decimal("10.00"), currency),
        source="test",
        source_kind="demo",
        variant_key=variant,
    )


def test_different_currencies_are_not_comparable() -> None:
    assert not comparable(snap("BRL"), snap("USD"))


def test_different_variants_are_not_comparable() -> None:
    assert not comparable(snap("BRL", "red"), snap("BRL", "blue"))
