import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch, errorText } from '../lib/api'
import { formatDate } from '../lib/format'
import type { SeasonDetail } from '../lib/types'

interface SourceRow {
  source: 'sonarr' | 'anilist' | 'tvmaze' | 'tmdb' | 'trakt' | 'override'
  count: number | null
  url?: string
  detail?: {
    listed: number
    unmonitored?: number
    aired: number
    on_disk: number
    finale: number | null
  }
  entries?: {
    id: number
    title: string | null
    episodes: number | null
    status: string | null
    url: string
  }[]
  parts?: { index: number; from: number; to: number; title: string }[]
}

interface CountSourcesView {
  expected: number | null
  expected_source: string | null
  disputed: boolean
  last_evaluated_at: string | null
  sources: SourceRow[]
}

function Note({ row }: { row: SourceRow }) {
  const { t } = useTranslation()
  if (row.source === 'sonarr' && row.detail) {
    return (
      <>
        {t('count.sonarrDetail', row.detail)}
        {Boolean(row.detail.unmonitored) &&
          ` · ${t('count.unmonitored', { count: row.detail.unmonitored })}`}
        {row.detail.finale !== null && ` · ${t('count.sonarrFinale', { n: row.detail.finale })}`}
      </>
    )
  }
  if (row.source === 'anilist') {
    return (
      <ul>
        {row.entries?.map((entry) => (
          <li key={entry.id}>
            <a href={entry.url} target="_blank" rel="noreferrer noopener" className="underline">
              {entry.title
                ? t('count.anilistEntry', {
                    title: entry.title,
                    episodes: entry.episodes ?? t('count.unknownCount'),
                    status: entry.status
                      ? t(`count.status.${entry.status}`, { defaultValue: entry.status })
                      : '?',
                  })
                : t('count.anilistEntryUnknown', { id: entry.id })}
            </a>
          </li>
        ))}
        {row.parts?.map((part) => (
          <li key={part.index}>{t('count.part', part)}</li>
        ))}
      </ul>
    )
  }
  return null
}

/** Every source's episode count for a season and the number Finalarr goes with. */
export function CountSources({ season }: { season: SeasonDetail }) {
  const { t, i18n } = useTranslation()
  const unclear = season.disputed || season.expected === null
  const [open, setOpen] = useState(unclear)
  const data = useQuery({
    queryKey: ['seasons', season.id, 'count-sources'],
    queryFn: () => apiFetch<CountSourcesView>(`/api/v1/seasons/${season.id}/count-sources`),
    enabled: open,
  })
  const view = data.data
  return (
    <details
      className="mt-3 text-sm"
      open={open}
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className="cursor-pointer text-muted hover:text-ink">{t('count.title')}</summary>
      {data.isError && <p className="mt-2 text-bad">{errorText(t, data.error)}</p>}
      {view && (
        <div className="mt-2 flex flex-col gap-2">
          <p className="font-bold">
            {view.expected && view.expected_source
              ? t('count.decision', {
                  n: view.expected,
                  source: t(`season.source.${view.expected_source}`),
                })
              : t('count.decisionUnknown')}
          </p>
          {view.disputed && <p className="text-bad">{t('count.disputedHint')}</p>}
          <table className="w-full max-w-2xl text-left">
            <thead className="text-xs text-muted">
              <tr>
                <th className="py-1 pr-3 font-normal">{t('count.source')}</th>
                <th className="py-1 pr-3 font-normal">{t('count.episodes')}</th>
                <th className="py-1 font-normal">{t('count.note')}</th>
              </tr>
            </thead>
            <tbody>
              {view.sources.map((row) => (
                <tr key={row.source} className="border-t border-line align-top">
                  <td className="py-1.5 pr-3">
                    {row.url ? (
                      <a
                        href={row.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="underline"
                      >
                        {t(`count.names.${row.source}`)}
                      </a>
                    ) : (
                      t(`count.names.${row.source}`)
                    )}
                  </td>
                  <td className="py-1.5 pr-3 font-bold">{row.count ?? t('count.unknownCount')}</td>
                  <td className="py-1.5 text-muted">
                    <Note row={row} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {view.last_evaluated_at && (
            <p className="text-xs text-muted">
              {t('count.checked', {
                time: formatDate(view.last_evaluated_at, i18n.language, true),
              })}
            </p>
          )}
        </div>
      )}
    </details>
  )
}
