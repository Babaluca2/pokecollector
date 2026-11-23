import { useEffect, useState } from 'react'
import { Scale } from 'lucide-react'
import Modal from './ui/Modal'
import MoneyInput from './MoneyInput'
import { useSettings } from '../contexts/SettingsContext'
import { formatMoneyInputValue, parseMoneyInputValue } from '../utils/moneyInput'

/**
 * Asks which price to keep for a card whose Cardmarket and TCGPlayer prices
 * differ a lot. Shown once, right after the card is saved; the choice can be
 * changed at any time from the card's edit form.
 *
 * Props:
 *   item      the collection item returned by the API (with price_comparison)
 *   onChoose  ({ price_source, price_override? }) => void  — user picked a price
 *   onKeepDefault  () => void — user closed or kept the default market
 *   isPending boolean
 */
export default function PriceChoiceDialog({ item, onChoose, onKeepDefault, isPending = false }) {
  const { t, formatPrice, exchangeRate, exchangeRateReady, settings } = useSettings()
  const [manual, setManual] = useState('')
  const comparison = item?.price_comparison
  const defaultMarket = settings?.price_market === 'tcgplayer' ? 'tcgplayer' : 'cardmarket'

  useEffect(() => {
    setManual(formatMoneyInputValue(item?.effective_price ?? null, exchangeRate))
  }, [item?.id, item?.effective_price, exchangeRate])

  if (!item || !comparison) return null

  const marketLabel = market => (market === 'tcgplayer' ? t('priceChoice.tcgplayer') : t('priceChoice.cardmarket'))
  const manualEur = parseMoneyInputValue(manual, exchangeRate, null)
  const options = [
    { market: 'cardmarket', value: comparison.cardmarket },
    { market: 'tcgplayer', value: comparison.tcgplayer },
  ]

  return (
    <Modal
      isOpen
      onClose={isPending ? undefined : onKeepDefault}
      title={t('priceChoice.title')}
      size="sm"
      mobileSheet
      overlayClassName="z-[400]"
    >
      <div className="space-y-4 p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid h-9 w-9 flex-shrink-0 place-items-center rounded-full bg-yellow/10 text-yellow">
            <Scale size={18} aria-hidden />
          </span>
          <p className="text-sm leading-relaxed text-text-secondary">
            {t('priceChoice.message')
              .replace('{name}', item.card?.name || '')
              .replace('{percent}', String(Math.round(comparison.difference_pct ?? 0)))}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {options.map(({ market, value }) => (
            <button
              key={market}
              type="button"
              disabled={isPending || value == null}
              onClick={() => onChoose({ price_source: market })}
              className="btn-secondary flex-col items-center justify-center gap-1 py-3"
            >
              <span className="text-xs text-text-muted">{marketLabel(market)}</span>
              <span className="text-lg font-semibold text-text-primary">{value != null ? formatPrice(value) : '—'}</span>
              {market === defaultMarket && (
                <span className="text-[10px] font-semibold  tracking-wide text-text-muted">{t('priceChoice.default')}</span>
              )}
            </button>
          ))}
        </div>

        <div className="space-y-2 border-t border-border pt-4">
          <label className="text-xs font-semibold text-text-muted" htmlFor="price-choice-manual">
            {t('priceChoice.manualLabel')}
          </label>
          <div className="flex gap-2">
            <MoneyInput
              id="price-choice-manual"
              value={manual}
              onChange={event => setManual(event.target.value)}
              wrapperClassName="flex-1"
            />
            <button
              type="button"
              className="btn-secondary"
              disabled={isPending || !exchangeRateReady || manualEur == null}
              onClick={() => onChoose({ price_source: 'manual', price_override: manualEur })}
            >
              {t('priceChoice.useManual')}
            </button>
          </div>
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-text-muted">{t('priceChoice.changeLater')}</p>
          <button type="button" className="btn-ghost w-full justify-center sm:w-auto" disabled={isPending} onClick={onKeepDefault}>
            {t('priceChoice.keepDefault').replace('{market}', marketLabel(defaultMarket))}
          </button>
        </div>
      </div>
    </Modal>
  )
}
