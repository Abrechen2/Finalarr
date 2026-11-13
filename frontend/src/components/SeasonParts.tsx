import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../lib/api'
import type { SeasonDetail } from '../lib/types'
import { Toggle } from './Toggle'

export function SeasonParts({ seriesId, season }: { seriesId: number; season: SeasonDetail }) {
  const { t } = useTranslation()
  const client = useQueryClient()
  const mode = useMutation({
    mutationFn: (parts_mode: 'season' | 'parts') =>
      apiFetch(`/api/v1/seasons/${season.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ parts_mode }),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['series', 'detail', seriesId] }),
  })
  if (season.parts.length < 2) return null
  return (
    <div className="mt-3">
      <h3 className="text-xs font-medium text-muted">{t('parts.title')}</h3>
      <ul className="mt-1 text-sm">
        {season.parts.map((p) => (
          <li key={p.index}>
            {t('parts.range', { index: p.index, from: p.from, to: p.to })}
            {p.title && <span className="text-muted"> · {p.title}</span>}
          </li>
        ))}
      </ul>
      <Toggle
        label={t('parts.asSeasons')}
        hint={t('parts.asSeasonsHint')}
        checked={season.parts_mode === 'parts'}
        disabled={mode.isPending}
        onChange={(checked) => mode.mutate(checked ? 'parts' : 'season')}
      />
    </div>
  )
}
