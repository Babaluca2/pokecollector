export const PRICE_PRIMARY_TO_FIELD = {
  market: 'price_market',
  avg: 'price_market',
  trend: 'price_trend',
  avg1: 'price_avg1',
  avg7: 'price_avg7',
  avg30: 'price_avg30',
  low: 'price_low',
}

export const REVERSE_HOLO_VARIANTS = new Set(['Reverse Holo'])

export const HOLO_FIELD_MAP = {
  price_market: 'price_market_holo',
  price_trend: 'price_trend_holo',
  price_avg1: 'price_avg1_holo',
  price_avg7: 'price_avg7_holo',
  price_avg30: 'price_avg30_holo',
  price_low: 'price_low_holo',
}

export function priceFieldFromPrimary(pricePrimary) {
  return PRICE_PRIMARY_TO_FIELD[pricePrimary] || 'price_trend'
}

export function getCardPriceValue(card, priceKey) {
  const field = PRICE_PRIMARY_TO_FIELD[priceKey] || priceKey
  return card?.[field]
    ?? card?.cardmarket?.prices?.[priceKey]
    ?? card?.pricing?.cardmarket?.[priceKey]
    ?? null
}

function positivePrice(value) {
  if (value == null) return null
  const price = Number(value)
  return Number.isFinite(price) && price > 0 ? price : null
}

export function getEffectiveCardPrice(card, variant, priceField = 'price_trend') {
  if (!card) return 0
  if (REVERSE_HOLO_VARIANTS.has(variant)) {
    const holoField = HOLO_FIELD_MAP[priceField]
    const candidates = [
      holoField ? card[holoField] : null,
      card[priceField],
      card.price_market_holo,
      card.price_market,
    ]
    for (const candidate of candidates) {
      const price = positivePrice(candidate)
      if (price != null) return price
    }
    return 0
  }

  for (const candidate of [card[priceField], card.price_market]) {
    const price = positivePrice(candidate)
    if (price != null) return price
  }
  return 0
}

export function getPrimaryCardPrice(card, variant, pricePrimary = 'trend', priceField = priceFieldFromPrimary(pricePrimary)) {
  const effectivePrice = getEffectiveCardPrice(card, variant, priceField)
  if (effectivePrice > 0) return effectivePrice
  return getCardPriceValue(card, pricePrimary)
}

export const PRICE_SOURCES = ['cardmarket', 'tcgplayer', 'manual']

/**
 * Unit price (EUR) of one owned copy.
 *
 * The API values each copy from its pinned market, a manual price, or the
 * user's default market (`effective_price`). That answer only applies to the
 * user's saved price statistic, so an explicit different `priceField`
 * (e.g. sorting by trend) falls back to the Cardmarket card prices.
 */
export function getCollectionItemPrice(item, priceField = 'price_trend', primaryField = priceField) {
  if (!item) return 0
  const isPrimaryField = priceField === primaryField
  if (isPrimaryField && item.effective_price != null && Number.isFinite(Number(item.effective_price))) {
    return Number(item.effective_price)
  }
  if (item.price_source === 'manual' && item.price_override != null) return Number(item.price_override)
  return getEffectiveCardPrice(item.card, item.variant, priceField)
}

/** True when the item's two market prices differ a lot and the user never chose one. */
export function needsPriceChoice(item) {
  return Boolean(item?.needs_price_choice)
}
