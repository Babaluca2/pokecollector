"""Per-user pricing context: price statistic, default market, exchange rate."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy.orm import Session

from models import UserSetting
from services.card_values import (
    DEFAULT_DIVERGENCE_PCT,
    MARKET_CARDMARKET,
    compare_markets,
    normalize_default_market,
    normalize_divergence_pct,
    normalize_price_field,
    resolve_item_price,
)

logger = logging.getLogger(__name__)


_ACTIVE_CONTEXT: ContextVar["PriceContext | None"] = ContextVar("active_price_context", default=None)


@contextmanager
def use_price_context(ctx: "PriceContext"):
    """Make ``ctx`` the pricing choice for helpers that have no db/user at hand."""
    token = _ACTIVE_CONTEXT.set(ctx)
    try:
        yield ctx
    finally:
        _ACTIVE_CONTEXT.reset(token)


def active_price_context() -> "PriceContext | None":
    return _ACTIVE_CONTEXT.get()


class PriceContext:
    """Pricing choices for one user. The USD->EUR rate is fetched lazily, once."""

    def __init__(
        self,
        price_field: str = "price_trend",
        default_market: str = MARKET_CARDMARKET,
        divergence_pct: float = DEFAULT_DIVERGENCE_PCT,
        usd_to_eur: float | None = None,
        *,
        fetch_rate: bool = True,
    ):
        self.price_field = price_field
        self.default_market = default_market
        self.divergence_pct = divergence_pct
        self._rate = usd_to_eur
        self._rate_loaded = usd_to_eur is not None or not fetch_rate

    def usd_to_eur(self) -> float | None:
        if not self._rate_loaded:
            self._rate = get_usd_to_eur_rate()
            self._rate_loaded = True
        return self._rate

    def resolve(self, item) -> tuple[float, str | None]:
        return resolve_item_price(item, self.price_field, self.default_market, self.usd_to_eur)

    def price(self, item) -> float:
        return self.resolve(item)[0]

    def price_for_card(self, card, variant=None) -> float:
        """Unit price of a card that has no collection row, using the default market."""
        from types import SimpleNamespace

        return self.price(SimpleNamespace(card=card, variant=variant, price_source=None, price_override=None))

    def comparison(self, item) -> dict:
        return compare_markets(
            getattr(item, "card", None),
            getattr(item, "variant", None),
            self.price_field,
            self.usd_to_eur(),
            self.divergence_pct,
        )


def get_usd_to_eur_rate() -> float | None:
    """Return the cached USD->EUR rate, or None when no rate is available."""
    try:
        from services.exchange_rates import get_exchange_rate

        rate = float(get_exchange_rate("USD", "EUR")["rate"])
        return rate if rate > 0 else None
    except Exception as exc:  # network or cache problems must never break valuation
        logger.warning("USD->EUR rate unavailable, TCGPlayer prices ignored: %s", exc)
        return None


def _setting(db: Session, user_id: int | None, key: str, default: str) -> str:
    if user_id is None:
        return default
    row = db.query(UserSetting).filter(
        UserSetting.user_id == user_id,
        UserSetting.key == key,
    ).first()
    return row.value if row and row.value not in (None, "") else default


def build_price_context(
    db: Session,
    user_id: int | None,
    *,
    price_field: str | None = None,
    usd_to_eur: float | None = None,
    fetch_rate: bool = True,
) -> PriceContext:
    """Build the pricing context for one user.

    ``price_field`` overrides the stored statistic (several endpoints accept it
    as a query parameter). The exchange rate is looked up once per context.
    """
    field = normalize_price_field(price_field or _setting(db, user_id, "price_primary", "trend"))
    market = normalize_default_market(_setting(db, user_id, "price_market", MARKET_CARDMARKET))
    pct = normalize_divergence_pct(_setting(db, user_id, "price_divergence_pct", str(DEFAULT_DIVERGENCE_PCT)))
    return PriceContext(field, market, pct, usd_to_eur, fetch_rate=fetch_rate)
