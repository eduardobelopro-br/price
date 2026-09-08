from decimal import Decimal

import pytest

from pricewatch.domain.models import Money


def test_money_normalizes_currency() -> None:
    money = Money(Decimal("19.90"), "brl")
    assert money.currency == "BRL"


def test_money_rejects_negative() -> None:
    with pytest.raises(ValueError):
        Money(Decimal("-1"), "BRL")
