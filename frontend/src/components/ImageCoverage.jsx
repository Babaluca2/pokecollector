import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getImageCoverage, repairImages } from '../api/client'
import { useSettings } from '../contexts/SettingsContext'

/** Compact audit of cards that have no artwork, per language and per set. */
export default function ImageCoverage() {
  const { t } = useSettings()
  const queryClient = useQueryClient()
  const repair = useMutation({
    mutationFn: repairImages,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['image-coverage'] })
      queryClient.invalidateQueries({ queryKey: ['cards'] })
    },
  })
  const { data, isLoading } = useQuery({
    queryKey: ['image-coverage'],
    queryFn: getImageCoverage,
    staleTime: 60_000,
  })
  if (isLoading || !data) return null
  const languages = data.languages || []
  const sets = (data.sets || []).slice(0, 8)
  return (
    <div className="px-1 py-3 text-sm">
      <p className="font-serif text-base">{t('settings.imageCoverage')}</p>
      <p className="text-xs text-text-muted mb-2">{t('settings.imageCoverageDesc')}</p>
      <div className="flex items-center gap-3 mb-2">
        <button type="button" className="btn-secondary text-xs" disabled={repair.isPending} onClick={() => repair.mutate()}>
          {repair.isPending ? t('settings.imageRepairRunning') : t('settings.imageRepair')}
        </button>
        {repair.data && (
          <span className="text-xs text-text-muted">
            {t('settings.imageRepairResult', { repaired: repair.data.repaired, remaining: repair.data.still_missing })}
          </span>
        )}
      </div>
      <ul className="divide-y divide-border">
        {languages.map(row => (
          <li key={row.lang} className="flex justify-between py-2">
            <span>{row.lang.toUpperCase()}</span>
            <span className={row.missing ? 'text-text-primary' : 'text-text-muted'}>
              {row.missing} / {row.total} ({row.missing_pct} %)
            </span>
          </li>
        ))}
      </ul>
      {sets.length > 0 && (
        <>
          <p className="mt-3 text-xs text-text-muted">{t('settings.imageCoverageWorst')}</p>
          <ul className="text-xs text-text-secondary">
            {sets.map(row => (
              <li key={`${row.lang}-${row.set_id}`} className="flex justify-between py-1">
                <span>{row.set_id} · {row.lang.toUpperCase()}</span>
                <span>{row.missing} / {row.total}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
