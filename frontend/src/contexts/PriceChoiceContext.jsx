import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import PriceChoiceDialog from '../components/PriceChoiceDialog'
import { updateCollectionItem, getApiErrorMessage } from '../api/client'
import { invalidateCardState } from '../utils/queryInvalidation'
import { useSettings } from './SettingsContext'
import { needsPriceChoice } from '../utils/prices'

const PriceChoiceContext = createContext(null)

/**
 * Lets any "add to collection" flow ask, once, which market price to keep when
 * Cardmarket and TCGPlayer differ a lot. Closing the dialog keeps the default
 * market and pins it, so the same copy is never asked about again.
 */
export function PriceChoiceProvider({ children }) {
  const { t, settings } = useSettings()
  const queryClient = useQueryClient()
  const [item, setItem] = useState(null)

  const mutation = useMutation({
    mutationFn: ({ itemId, choice }) => updateCollectionItem(itemId, choice),
    onSuccess: () => {
      setItem(null)
      invalidateCardState(queryClient)
      toast.success(t('priceChoice.saved'))
    },
    onError: (error) => toast.error(getApiErrorMessage(error, t('priceChoice.saveFailed'))),
  })

  /** Call with the collection item returned by the add endpoint. */
  const promptPriceChoice = useCallback((addedItem) => {
    if (needsPriceChoice(addedItem)) setItem(addedItem)
  }, [])

  const keepDefault = useCallback(() => {
    if (!item) return
    const market = settings?.price_market === 'tcgplayer' ? 'tcgplayer' : 'cardmarket'
    mutation.mutate({ itemId: item.id, choice: { price_source: market } })
  }, [item, mutation, settings?.price_market])

  const value = useMemo(() => promptPriceChoice, [promptPriceChoice])

  return (
    <PriceChoiceContext.Provider value={value}>
      {children}
      <PriceChoiceDialog
        item={item}
        isPending={mutation.isPending}
        onChoose={choice => mutation.mutate({ itemId: item.id, choice })}
        onKeepDefault={keepDefault}
      />
    </PriceChoiceContext.Provider>
  )
}

export function usePriceChoicePrompt() {
  const prompt = useContext(PriceChoiceContext)
  // Outside the provider (tests, isolated renders) prompting is a no-op.
  return prompt || (() => {})
}
