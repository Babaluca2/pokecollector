import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Minus, Plus, X } from 'lucide-react'
import Modal from './ui/Modal'
import { searchCards } from '../api/client'
import { useSettings } from '../contexts/SettingsContext'

const ALLOCATIONS = ['equal', 'value', 'none']

/**
 * Open a sealed product: pick the cards pulled from it, choose how its price
 * is spread over them, and send everything in one go.
 */
export default function OpenProductDialog({ isOpen, product, onClose, onOpen, loading = false }) {
  const { t, formatPrice } = useSettings()
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState([])
  const [allocation, setAllocation] = useState('equal')
  const trimmed = query.trim()

  const { data: results = [] } = useQuery({
    queryKey: ['open-product-search', trimmed],
    queryFn: () => searchCards({ q: trimmed, page_size: 8, lang: 'all' }).then(r => r.data?.data || []),
    enabled: trimmed.length >= 2,
    placeholderData: prev => prev,
  })

  const add = (card) => setPicked(current => {
    const found = current.find(entry => entry.card.id === card.id)
    if (found) return current.map(entry => (entry.card.id === card.id ? { ...entry, quantity: entry.quantity + 1 } : entry))
    return [...current, { card, quantity: 1 }]
  })
  const change = (id, delta) => setPicked(current => current
    .map(entry => (entry.card.id === id ? { ...entry, quantity: entry.quantity + delta } : entry))
    .filter(entry => entry.quantity > 0))
  const copies = picked.reduce((sum, entry) => sum + entry.quantity, 0)

  const submit = async () => {
    await onOpen({
      allocation,
      cards: picked.map(({ card, quantity }) => ({ card_id: card.id, quantity, lang: card.lang || 'en' })),
    })
    setPicked([])
    setQuery('')
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={t('products.openTitle').replace('{product}', product?.product_name || '')} size="lg" mobileSheet>
      <div className="space-y-5 p-5">
        <div>
          <label htmlFor="open-product-search" className="text-sm text-text-secondary">{t('products.openSearch')}</label>
          <input id="open-product-search" className="input mt-1 px-3 py-2.5 text-sm" value={query}
            onChange={e => setQuery(e.target.value)} placeholder={t('products.openSearchPlaceholder')} />
          {results.length > 0 && trimmed.length >= 2 && (
            <ul className="mt-2 border border-border rounded-lg divide-y divide-border max-h-56 overflow-y-auto">
              {results.map(card => (
                <li key={card.id}>
                  <button type="button" onClick={() => add(card)}
                    className="flex w-full min-h-[44px] items-center justify-between gap-3 px-3 text-left text-sm hover:bg-bg-elevated">
                    <span className="truncate">{card.name} <span className="text-text-muted">#{card.number} · {card.set_ref?.name || card.set_id} · {(card.lang || 'en').toUpperCase()}</span></span>
                    <Plus size={14} aria-hidden="true" className="shrink-0 text-brand-red" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {picked.length > 0 && (
          <ul className="border-t border-border">
            {picked.map(({ card, quantity }) => (
              <li key={card.id} className="flex items-center justify-between gap-3 min-h-[48px] border-b border-border text-sm">
                <span className="truncate">{card.name} <span className="text-text-muted">#{card.number} · {(card.lang || 'en').toUpperCase()}</span></span>
                <span className="flex items-center gap-1 shrink-0">
                  <button type="button" aria-label={t('products.openLess')} onClick={() => change(card.id, -1)} className="grid h-9 w-9 place-items-center text-text-secondary hover:text-text-primary">
                    {quantity === 1 ? <X size={14} /> : <Minus size={14} />}
                  </button>
                  <span className="w-6 text-center">{quantity}</span>
                  <button type="button" aria-label={t('products.openMore')} onClick={() => change(card.id, 1)} className="grid h-9 w-9 place-items-center text-text-secondary hover:text-text-primary">
                    <Plus size={14} />
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}

        <fieldset className="space-y-2">
          <legend className="text-sm text-text-secondary">
            {t('products.openAllocation').replace('{price}', formatPrice(product?.purchase_price || 0))}
          </legend>
          {ALLOCATIONS.map(mode => (
            <label key={mode} className="flex min-h-[44px] items-start gap-3 text-sm cursor-pointer">
              <input type="radio" name="open-allocation" className="mt-1" checked={allocation === mode} onChange={() => setAllocation(mode)} />
              <span>
                <span className="block text-text-primary">{t(`products.openAllocation_${mode}`)}</span>
                <span className="block text-xs text-text-muted">{t(`products.openAllocation_${mode}_help`)}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <button type="button" disabled={loading || picked.length === 0} onClick={submit} className="btn-primary w-full min-h-[44px]">
          {t('products.openConfirm').replace('{count}', String(copies))}
        </button>
      </div>
    </Modal>
  )
}
