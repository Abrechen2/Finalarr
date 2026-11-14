import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch, errorText } from '../lib/api'
import { pad } from '../lib/episodes'
import type { SeasonDetail, SeriesDetail, WatchState } from '../lib/types'
import { EpisodeGrid } from './EpisodeGrid'

const BUTTON = 'rounded-control border border-line px-2.5 py-1 text-xs hover:border-accent'

/** The episode grid with watched marks; with a media server connected, clicking an
 *  episode corrects its watched state for one person. */
export function WatchCorrector({ series, season }: { series: SeriesDetail; season: SeasonDetail }) {
  const { t } = useTranslation()
  const client = useQueryClient()
  const watch = series.watch
  const viewers = watch?.viewers ?? []
  const [selected, setSelected] = useState<number | undefined>()
  const [userId, setUserId] = useState<number | undefined>(viewers[0]?.id)
  const names = Object.fromEntries(viewers.map((v) => [v.id, v.name]))
  const watched = Object.fromEntries(
    Object.entries(watch?.episodes ?? {}).map(([key, ids]) => [
      key,
      ids.map((id) => names[id] ?? '?'),
    ]),
  )
  const correct = useMutation({
    mutationFn: (body: { episodes: [number, number][]; watched: boolean | null }) =>
      apiFetch<WatchState>(`/api/v1/series/${series.id}/watched`, {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, ...body }),
      }),
    onSuccess: (state) => {
      client.setQueryData<SeriesDetail>(['series', 'detail', series.id], (old) =>
        old ? { ...old, watch: state } : old,
      )
      setSelected(undefined)
    },
  })
  const interactive = Boolean(watch?.enabled && viewers.length && userId !== undefined)
  const numbers = season.episodes.map((e) => e.number)
  const pairs = (list: number[]): [number, number][] => list.map((n) => [season.number, n])
  const key = selected !== undefined ? `${season.number}x${selected}` : ''
  return (
    <>
      <EpisodeGrid
        season={season.number}
        episodes={season.episodes}
        partStarts={season.parts.slice(1).map((p) => p.from)}
        watched={watched}
        corrected={watch?.corrected}
        selected={selected}
        onSelect={interactive ? (n) => setSelected(n === selected ? undefined : n) : undefined}
      />
      {interactive && selected === undefined && (
        <p className="mt-2 text-xs text-muted">{t('watch.correctHint')}</p>
      )}
      {interactive && selected !== undefined && (
        <div
          role="group"
          aria-label={t('watch.correctTitle', { s: pad(season.number), e: pad(selected) })}
          className="mt-3 flex flex-wrap items-center gap-2 rounded-card border border-line p-3 text-sm"
        >
          <span className="font-bold">
            {t('watch.correctTitle', { s: pad(season.number), e: pad(selected) })}
          </span>
          {viewers.length > 1 && (
            <label className="flex items-center gap-1 text-xs text-muted">
              {t('watch.correctFor')}
              <select
                value={userId}
                onChange={(e) => setUserId(Number(e.target.value))}
                className="rounded-control border border-line bg-bg px-1 py-0.5 text-sm text-ink"
              >
                {viewers.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            type="button"
            className={BUTTON}
            disabled={correct.isPending}
            onClick={() => correct.mutate({ episodes: pairs([selected]), watched: true })}
          >
            {t('watch.markWatched')}
          </button>
          <button
            type="button"
            className={BUTTON}
            disabled={correct.isPending}
            onClick={() => correct.mutate({ episodes: pairs([selected]), watched: false })}
          >
            {t('watch.markUnwatched')}
          </button>
          <button
            type="button"
            className={BUTTON}
            disabled={correct.isPending}
            onClick={() =>
              correct.mutate({
                episodes: pairs(numbers.filter((n) => n <= selected)),
                watched: true,
              })
            }
          >
            {t('watch.markUpTo')}
          </button>
          <button
            type="button"
            className={BUTTON}
            disabled={correct.isPending}
            onClick={() => correct.mutate({ episodes: pairs(numbers), watched: true })}
          >
            {t('watch.markSeason')}
          </button>
          <button
            type="button"
            className={BUTTON}
            disabled={correct.isPending}
            onClick={() => correct.mutate({ episodes: pairs(numbers), watched: false })}
          >
            {t('watch.unmarkSeason')}
          </button>
          {watch?.corrected.includes(key) && (
            <button
              type="button"
              className={BUTTON}
              disabled={correct.isPending}
              onClick={() => correct.mutate({ episodes: pairs([selected]), watched: null })}
            >
              {t('watch.undo')}
            </button>
          )}
          <button
            type="button"
            className="text-xs text-muted hover:text-ink"
            onClick={() => setSelected(undefined)}
          >
            {t('watch.close')}
          </button>
          {correct.isError && <p className="w-full text-bad">{errorText(t, correct.error)}</p>}
        </div>
      )}
    </>
  )
}
