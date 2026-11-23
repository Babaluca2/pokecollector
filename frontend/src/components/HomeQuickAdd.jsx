import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, Search } from 'lucide-react'
import UnifiedCardScanner from './UnifiedCardScanner'
import { useSettings } from '../contexts/SettingsContext'

/** Home entry point: scan a card, or type a set and/or card name with its number. */
export default function HomeQuickAdd() {
  const { t } = useSettings()
  const navigate = useNavigate()
  const [value, setValue] = useState('')
  const [scannerOpen, setScannerOpen] = useState(false)

  const submit = (event) => {
    event.preventDefault()
    const q = value.trim()
    navigate(q ? `/search?q=${encodeURIComponent(q)}` : '/search')
  }

  return (
    <section aria-label={t('home.quickAdd')}>
      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row">
        <button type="button" onClick={() => setScannerOpen(true)}
          className="btn-primary min-h-[44px] justify-center gap-2 sm:w-auto">
          <Camera size={16} aria-hidden="true" />{t('home.scan')}
        </button>
        <span className="self-center text-xs text-text-muted text-center">{t('home.or')}</span>
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden="true" />
          <input
            type="search"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={t('home.quickSearchPlaceholder')}
            aria-label={t('home.quickSearchPlaceholder')}
            className="input w-full min-h-[44px] pl-9"
          />
        </div>
      </form>
      <UnifiedCardScanner
        isOpen={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onCardSelected={(card) => {
          setScannerOpen(false)
          navigate(`/search?q=${encodeURIComponent(card.name)}`)
        }}
      />
    </section>
  )
}
