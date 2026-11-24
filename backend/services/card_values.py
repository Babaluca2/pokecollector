VALID_PRICE_FIELDS = {"price_market", "price_trend", "price_avg1", "price_avg7", "price_avg30", "price_low"}
PRICE_PRIMARY_TO_FIELD = {
    "market": "price_market",
    "avg": "price_market",
    "trend": "price_trend",
    "avg1": "price_avg1",
    "avg7": "price_avg7",
    "avg30": "price_avg30",
    "low": "price_low",
}
REVERSE_HOLO_VARIANTS = {"Reverse Holo"}
HOLO_FIELD_MAP = {
    "price_market": "price_market_holo",
    "price_trend": "price_trend_holo",
    "price_avg1": "price_avg1_holo",
    "price_avg7": "price_avg7_holo",
    "price_avg30": "price_avg30_holo",
    "price_low": "price_low_holo",
}


def normalize_price_field(price_field: str | None) -> str:
    if not price_field:
        return "price_trend"
    value = str(price_field)
    field = PRICE_PRIMARY_TO_FIELD.get(value, value)
    return field if field in VALID_PRICE_FIELDS else "price_trend"


def _positive_price(value) -> float | None:
    """Return a usable Cardmarket price, treating missing/zero values as unavailable."""
    if value is None:
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def effective_market_price(card, variant=None, price_field: str | None = "price_trend") -> float:
    """Return the selected Cardmarket EUR price for a card.

    TCGdex/Cardmarket may report unavailable reverse-holo prices as 0 instead of null.
    The ``*-holo`` price fields represent Cardmarket's alternate/reverse listing,
    not every card whose printed finish is Holo. Treat zero values as missing so
    Reverse Holo can fall back to the selected base price instead of being valued
    at €0.
    """
    if not card:
        return 0
    field = normalize_price_field(price_field)
    if variant in REVERSE_HOLO_VARIANTS:
        holo_field = HOLO_FIELD_MAP.get(field)
        for candidate in (
            getattr(card, holo_field, None) if holo_field else None,
            getattr(card, field, None),
            getattr(card, "price_market_holo", None),
            getattr(card, "price_market", None),
        ):
            price = _positive_price(candidate)
            if price is not None:
                return price
        return 0

    for candidate in (getattr(card, field, None), getattr(card, "price_market", None)):
        price = _positive_price(candidate)
        if price is not None:
            return price
    return 0


# ---------------------------------------------------------------------------
# Multi-market pricing
#
# Card rows store Cardmarket prices in EUR and TCGPlayer prices in USD. A
# collection item may pin the market used to value that physical copy
# (``price_source``) or carry a manual EUR price (``price_override``). When
# nothing is pinned, the user's default market applies.
# ---------------------------------------------------------------------------

MARKET_CARDMARKET = "cardmarket"
MARKET_TCGPLAYER = "tcgplayer"
MARKET_MANUAL = "manual"
VALID_DEFAULT_MARKETS = {MARKET_CARDMARKET, MARKET_TCGPLAYER}
VALID_ITEM_PRICE_SOURCES = {MARKET_CARDMARKET, MARKET_TCGPLAYER, MARKET_MANUAL}

# A pair of markets "diverges" when they differ by at least this percentage of
# the cheaper price AND by at least MIN_DIVERGENCE_EUR (so that a 0.05 vs 0.12
# bulk card does not raise a warning).
DEFAULT_DIVERGENCE_PCT = 50.0
MIN_DIVERGENCE_EUR = 1.0

_TCGPLAYER_FIELDS_BY_VARIANT = {
    "Reverse Holo": ("price_tcg_reverse_market", "price_tcg_holo_market", "price_tcg_normal_market"),
    "Holo": ("price_tcg_holo_market", "price_tcg_normal_market", "price_tcg_reverse_market"),
    "Normal": ("price_tcg_normal_market", "price_tcg_holo_market", "price_tcg_reverse_market"),
    "First Edition": ("price_tcg_normal_market", "price_tcg_holo_market", "price_tcg_reverse_market"),
}


def normalize_default_market(value: str | None) -> str:
    value = (value or "").strip().lower()
    return value if value in VALID_DEFAULT_MARKETS else MARKET_CARDMARKET


def normalize_item_price_source(value: str | None) -> str | None:
    """Return a valid per-item source, or None when the item follows the default."""
    if value is None:
        return None
    value = str(value).strip().lower()
    if not value:
        return None
    if value not in VALID_ITEM_PRICE_SOURCES:
        raise ValueError(f"price_source must be one of: {', '.join(sorted(VALID_ITEM_PRICE_SOURCES))}")
    return value


def normalize_divergence_pct(value) -> float:
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return DEFAULT_DIVERGENCE_PCT
    return pct if pct > 0 else DEFAULT_DIVERGENCE_PCT


def tcgplayer_price_usd(card, variant=None) -> float | None:
    """Return the TCGPlayer market price (USD) for the printed finish, or None."""
    if not card:
        return None
    fields = _TCGPLAYER_FIELDS_BY_VARIANT.get(variant) or _TCGPLAYER_FIELDS_BY_VARIANT["Normal"]
    for field in fields:
        price = _positive_price(getattr(card, field, None))
        if price is not None:
            return price
    return None


def cardmarket_price_eur(card, variant=None, price_field: str | None = "price_trend") -> float | None:
    price = effective_market_price(card, variant, price_field)
    return price if price and price > 0 else None


def tcgplayer_price_eur(card, variant=None, usd_to_eur=None) -> float | None:
    """TCGPlayer price in EUR. ``usd_to_eur`` may be a rate or a callable returning one."""
    usd = tcgplayer_price_usd(card, variant)
    if usd is None:
        return None
    rate = usd_to_eur() if callable(usd_to_eur) else usd_to_eur
    if not rate or rate <= 0:
        return None
    return usd * rate


def compare_markets(
    card,
    variant=None,
    price_field: str | None = "price_trend",
    usd_to_eur=None,
    threshold_pct: float = DEFAULT_DIVERGENCE_PCT,
) -> dict:
    """Return both market prices (EUR) and whether they differ too much."""
    cardmarket = cardmarket_price_eur(card, variant, price_field)
    tcgplayer = tcgplayer_price_eur(card, variant, usd_to_eur)
    difference_pct = None
    diverges = False
    if cardmarket is not None and tcgplayer is not None:
        low, high = sorted((cardmarket, tcgplayer))
        difference_pct = (high - low) / low * 100
        diverges = difference_pct >= threshold_pct and (high - low) >= MIN_DIVERGENCE_EUR
    return {
        "cardmarket": round(cardmarket, 2) if cardmarket is not None else None,
        "tcgplayer": round(tcgplayer, 2) if tcgplayer is not None else None,
        "difference_pct": round(difference_pct, 1) if difference_pct is not None else None,
        "diverges": diverges,
    }


def resolve_item_price(
    item,
    price_field: str | None = "price_trend",
    default_market: str | None = MARKET_CARDMARKET,
    usd_to_eur=None,
) -> tuple[float, str | None]:
    """Return ``(price_eur, market_used)`` for one collection item.

    Order: manual override, the item's pinned market, the user's default market.
    If the chosen automatic market has no price, the other one is used so the
    card is not valued at zero; ``market_used`` reports what was actually used.
    """
    card = getattr(item, "card", None)
    variant = getattr(item, "variant", None)
    source = getattr(item, "price_source", None)
    override = getattr(item, "price_override", None)

    if source == MARKET_MANUAL and override is not None and override >= 0:
        return float(override), MARKET_MANUAL

    wanted = source if source in VALID_DEFAULT_MARKETS else normalize_default_market(default_market)
    # Compute lazily so the exchange rate is only needed when TCGPlayer is used.
    getters = {
        MARKET_CARDMARKET: lambda: cardmarket_price_eur(card, variant, price_field),
        MARKET_TCGPLAYER: lambda: tcgplayer_price_eur(card, variant, usd_to_eur),
    }
    order = (
        (MARKET_TCGPLAYER, MARKET_CARDMARKET)
        if wanted == MARKET_TCGPLAYER
        else (MARKET_CARDMARKET, MARKET_TCGPLAYER)
    )
    for market in order:
        price = getters[market]()
        if price is not None:
            return price, market
    return 0, None


def effective_item_price(
    item,
    price_field: str | None = "price_trend",
    default_market: str | None = MARKET_CARDMARKET,
    usd_to_eur=None,
) -> float:
    return resolve_item_price(item, price_field, default_market, usd_to_eur)[0]
