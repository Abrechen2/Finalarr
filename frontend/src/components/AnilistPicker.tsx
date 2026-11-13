import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError, apiFetch, errorKey } from '../lib/api'
import type { SeasonDetail } from '../lib/types'

interface Candidate {
  id: number
  title: string
  romaji: string | null
  format: string | null
  status: string | null
  episodes: number | null
  start_date: string | null
}

const MAX_PICKS = 4

function friendly(error: unknown): string {
  return error instanceof ApiError && error.code === 'anilist_unavailable'
    ? 'anilist.unavailable'
    : errorKey(error)
}

/** AniList mapping of one season: shows the entries, lets the user search and pin. */
export function AnilistPicker({
  seriesId,
  seriesTitle,
  season,
}: {
  seriesId: number
  seriesTitle: string
  season: SeasonDetail
}) {
  const { t } = useTranslation()
  const client = useQueryClient()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState(seriesTitle)
  const [picked, setPicked] = useState<number[]>(season.anilist_ids)
  const search = useMutation({
    mutationFn: (q: string) =>
      apiFetch<Candidate[]>(`/api/v1/anilist/search?q=${encodeURIComponent(q)}`),
  })
  const save = useMutation({
    mutationFn: (ids: number[]) =>
      apiFetch<{ saved?: boolean }>(`/api/v1/seasons/${season.id}/anilist`, {
        method: 'PUT',
        body: JSON.stringify({ anilist_ids: ids }),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['series', 'detail', seriesId] }),
  })

  function toggle(id: number) {
    setPicked((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id].slice(0, MAX_PICKS),
    )
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    search.mutate(query)
  }

  const button = 'rounded-card border border-line px-3 py-1 text-xs text-muted hover:text-ink'
  const source = season.anilist_pinned ? t('anilist.manual') : t('anilist.auto')
  return (
    <div className="mt-3 text-sm">
      <p className="text-muted">
        {season.anilist_ids.length
          ? t('anilist.entries', { ids: season.anilist_ids.map((i) => `#${i}`).join(', '), source })
          : t('anilist.none')}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          className={button}
          onClick={() => setOpen(!open)}
          aria-expanded={open}
        >
          {t('anilist.assign')}
        </button>
        {season.anilist_pinned && (
          <button type="button" className={button} onClick={() => save.mutate([])}>
            {t('anilist.remove')}
          </button>
        )}
      </div>
      {open && (
        <div className="mt-3 rounded-card border border-line p-3">
          <form onSubmit={submit} className="flex flex-wrap gap-2">
            <input
              type="search"
              aria-label={t('anilist.search')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="min-w-48 flex-1 rounded-card border border-line bg-bg px-2 py-1"
            />
            <button type="submit" className={button} disabled={search.isPending}>
              {t('anilist.searchButton')}
            </button>
          </form>
          {search.isError && <p className="mt-2 text-bad">{t(friendly(search.error))}</p>}
          {search.data && (
            <>
              <p className="mt-2 text-xs text-muted">{t('anilist.pick')}</p>
              <ul className="mt-1 flex flex-col gap-1">
                {search.data.map((c) => (
                  <li key={c.id}>
                    <label className="flex cursor-pointer items-center gap-2">
                      <input
                        type="checkbox"
                        checked={picked.includes(c.id)}
                        onChange={() => toggle(c.id)}
                      />
                      <span>
                        {c.title} <span className="text-xs text-muted">#{c.id}</span>
                        <span className="block text-xs text-muted">
                          {[
                            c.format,
                            c.start_date?.slice(0, 4),
                            c.episodes && t('anilist.episodesShort', { n: c.episodes }),
                          ]
                            .filter(Boolean)
                            .join(' · ')}
                        </span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className={`${button} mt-2`}
                disabled={picked.length === 0 || save.isPending}
                onClick={() => save.mutate(picked)}
              >
                {t('anilist.save')}
              </button>
            </>
          )}
        </div>
      )}
      <p role="status" className="mt-1 text-xs">
        {save.data?.saved && <span className="text-warn">{t('anilist.savedLater')}</span>}
        {save.isError && <span className="text-bad">{t(friendly(save.error))}</span>}
      </p>
    </div>
  )
}
