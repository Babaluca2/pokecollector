import { describe, expect, it } from 'vitest'
import { getCollectionItemPrice, getEffectiveCardPrice } from './prices'

describe('Special variant pricing', () => {
  it('uses the ordinary Cardmarket selected field instead of Holo or Reverse pricing', () => {
    const card = {
      price_trend: 12.5,
      price_trend_holo: 25,
      price_market: 13,
      price_market_holo: 26,
    }

    expect(getEffectiveCardPrice(card, 'Special', 'price_trend')).toBe(12.5)
    expect(getEffectiveCardPrice(card, 'Reverse Holo', 'price_trend')).toBe(25)
  })
})

describe('getCollectionItemPrice', () => {
  const card = { price_trend: 10, price_market: 10 }

  it('uses the price computed by the API for the saved statistic', () => {
    expect(getCollectionItemPrice({ card, variant: 'Normal', effective_price: 18 }, 'price_trend', 'price_trend')).toBe(18)
  })

  it('falls back to Cardmarket card prices for another statistic', () => {
    expect(getCollectionItemPrice({ card, variant: 'Normal', effective_price: 18 }, 'price_trend', 'price_avg7')).toBe(10)
  })

  it('uses the manual price when the API value is missing', () => {
    expect(getCollectionItemPrice({ card, variant: 'Normal', price_source: 'manual', price_override: 3.5 }, 'price_trend', 'price_trend')).toBe(3.5)
  })

  it('keeps a manual price of zero', () => {
    expect(getCollectionItemPrice({ card, variant: 'Normal', effective_price: 0 }, 'price_trend', 'price_trend')).toBe(0)
  })

  it('handles a missing item', () => {
    expect(getCollectionItemPrice(null)).toBe(0)
  })
})
