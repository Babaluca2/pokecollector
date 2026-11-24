import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getImageCoverage, importChsCards, importJpCards, repairImages } from '../api/client'
import { useSettings } from '../contexts/SettingsContext'

/** Compact audit of cards that have no artwork, per language and per set. */
export default function ImageCoverage() {
  const { t } = useSettings()
  const queryClient = useQueryClient()
  const importChs = useMutation({
    mutationFn: importChsCards,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['image-coverage'] })
      queryClient.invalidateQueries({ queryKey: ['sets'] })
      queryClient.invalidateQueries({ queryKey: ['cards'] })
    },
  })
  const importJp = useMutation({
    mutationFn: importJpCards,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['image-coverage'] })
      queryClient.invalidateQueries({ queryKey: ['sets'] })
      queryClient.invalidateQueries({ queryKey: ['cards'] })
    },
  })
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
      <div className="flex flex-wrap items-center gap-3 mb-2">
        <button type="button" className="btn-secondary text-xs" disabled={repair.isPending} onClick={() => repair.mutate()}>
          {repair.isPending ? t('settings.imageRepairRunning') : t('settings.imageRepair')}
        </button>
        <button type="button" className="btn-secondary text-xs" disabled={importChs.isPending} onClick={() => importChs.mutate()}>
          {importChs.isPending ? t('settings.importChsRunning') : t('settings.importChs')}
        </button>
        <button type="button" className="btn-secondary text-xs" disabled={importJp.isPending} onClick={() => importJp.mutate()}>
          {importJp.isPending ? t('settings.importJpRunning') : t('settings.importJp')}
        </button>
        {importJp.data && (
          <span className="text-xs text-text-muted">
            {t('settings.importJpResult').replace('{filled}', importJp.data.filled).replace('{sets}', importJp.data.sets).replace('{cards}', importJp.data.cards)}
          </span>
        )}
        {importJp.isError && <span className="text-xs text-red-400">{t('settings.importJpError')}</span>}
        {importChs.data && (
          <span className="text-xs text-text-muted">
            {t('settings.importChsResult').replace('{sets}', importChs.data.sets).replace('{cards}', importChs.data.cards)}
          </span>
        )}
        {importChs.isError && <span className="text-xs text-red-400">{t('settings.importChsError')}</span>}
        {repair.data && (
          <span className="text-xs text-text-muted">
            {t('settings.imageRepairResult').replace('{repaired}', repair.data.repaired).replace('{remaining}', repair.data.still_missing)}
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
