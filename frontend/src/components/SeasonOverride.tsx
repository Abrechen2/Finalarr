import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch, errorKey } from '../lib/api'
import type { SeasonDetail } from '../lib/types'

export function SeasonOverride({ seriesId, season }: { seriesId: number; season: SeasonDetail }) {
  const { t } = useTranslation()
  const client = useQueryClient()
  const [value, setValue] = useState(season.expected_override?.toString() ?? '')
  const save = useMutation({
    mutationFn: (expected_override: number | null) =>
      apiFetch(`/api/v1/seasons/${season.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ expected_override }),
      }),
    onSuccess: (_data, override) => {
      setValue(override?.toString() ?? '')
      return client.invalidateQueries({ queryKey: ['series', 'detail', seriesId] })
    },
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate(value ? Number(value) : null)
  }

  const button = 'rounded-card border border-line px-3 py-1 text-xs text-muted hover:text-ink'
  return (
    <form onSubmit={submit} className="mt-3 flex flex-wrap items-end gap-2">
      <label className="flex flex-col text-xs text-muted">
        {t('rules.override')}
        <input
          type="number"
          min={1}
          max={2000}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="mt-1 w-24 rounded-card border border-line bg-bg px-2 py-1 font-mono text-sm text-ink"
        />
      </label>
      <button type="submit" className={button} disabled={save.isPending}>
        {t('rules.save')}
      </button>
      {season.expected_override !== null && (
        <button type="button" className={button} onClick={() => save.mutate(null)}>
          {t('rules.clear')}
        </button>
      )}
      {season.disputed && season.anilist_count && (
        <>
          <button
            type="button"
            className={button}
            onClick={() => save.mutate(season.anilist_count)}
          >
            {t('rules.takeAnilist', { n: season.anilist_count })}
          </button>
          <button
            type="button"
            className={button}
            onClick={() => save.mutate(season.episodes.length)}
          >
            {t('rules.takeSonarr', { n: season.episodes.length })}
          </button>
        </>
      )}
      <span role="status" className="text-xs">
        {save.isSuccess && <span className="text-ok">{t('rules.saved')}</span>}
        {save.isError && <span className="text-bad">{t(errorKey(save.error))}</span>}
      </span>
    </form>
  )
}
