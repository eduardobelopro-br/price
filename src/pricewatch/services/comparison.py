from pricewatch.domain.models import OfferSnapshot


def comparable(left: OfferSnapshot, right: OfferSnapshot) -> bool:
    if left.source_kind != right.source_kind:
        return False
    if left.price.currency != right.price.currency:
        return False
    if left.price_scope != right.price_scope:
        return False
    if left.variant_key != right.variant_key:
        return False
    return True
