import { useQuery } from '@tanstack/react-query'
import { Trophy } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { EmptyState, PageTitle } from '../components/EmptyState'
import { Poster } from '../components/Poster'
import { apiFetch, errorText } from '../lib/api'
import { pad } from '../lib/episodes'
import { relativeTime } from '../lib/format'

type State = 'behind' | 'abandoned' | 'caught_up' | 'finished' | 'unknown'
type Filter = 'all' | State
type Sort = 'recent' | 'open' | 'title'

interface Stats {
  episodes: number
  minutes: number
  undated: number
  this_week: number
  this_month: number
  weekly: { week: string; episodes: number }[]
  series: Record<'started' | State, number>
  users: { id: number; name: string; server: string }[]
}

interface Row {
  series_id: number
  title: string
  poster_url: string | null
  state: State
  watched: number
  unwatched: number | null
  next: { season: number; episode: number } | null
  last_watched: string | null
}

const FILTERS: Filter[] = ['all', 'behind', 'abandoned', 'caught_up', 'finished', 'unknown']
const SORTS: Sort[] = ['recent', 'open', 'title']
const CHART_HEIGHT = 120
const SELECT = 'rounded-card border border-line bg-bg px-2 py-1.5 text-sm'

function shortDate(iso: string, language: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(language === 'en' ? 'en-GB' : 'de-DE', {
    day: '2-digit',
    month: '2-digit',
  })
}

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 font-display text-2xl font-bold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  )
}

/** Episodes per week, oldest left. The busiest and the current week carry their number. */
function WeeklyChart({ weekly }: { weekly: Stats['weekly'] }) {
  const { t, i18n } = useTranslation()
  const max = Math.max(1, ...weekly.map((w) => w.episodes))
  const busiest = weekly.reduce((best, w, i) => (w.episodes > weekly[best].episodes ? i : best), 0)
  return (
    <section aria-labelledby="weekly" className="rounded-card border border-line bg-surface p-4">
      <h2 id="weekly" className="mb-4 text-sm text-muted">
        {t('tracker.weekly', { count: weekly.length })}
      </h2>
      <div className="flex items-end gap-1" style={{ height: CHART_HEIGHT + 20 }}>
        {weekly.map((w, i) => {
          const label = t('tracker.weekBar', {
            week: shortDate(w.week, i18n.language),
            count: w.episodes,
          })
          const labelled = w.episodes > 0 && (i === busiest || i === weekly.length - 1)
          return (
            <div
              key={w.week}
              role="img"
              aria-label={label}
              title={label}
              tabIndex={0}
              className="group flex h-full min-w-0 flex-1 flex-col items-center justify-end outline-none"
            >
              <span
                className={`mb-1 text-xs tabular-nums ${labelled ? 'text-ink' : 'text-transparent group-hover:text-ink group-focus-visible:text-ink'}`}
              >
                {w.episodes}
              </span>
              <span
                className={`w-full max-w-10 rounded-t-[4px] ${w.episodes ? 'bg-accent group-hover:opacity-80' : 'bg-line'} group-focus-visible:outline-2 group-focus-visible:outline-offset-2 group-focus-visible:outline-accent`}
                style={{ height: w.episodes ? Math.max(4, (w.episodes / max) * CHART_HEIGHT) : 2 }}
              />
            </div>
          )
        })}
      </div>
      <div className="mt-1 flex gap-1 border-t border-line pt-1 text-xs text-muted">
        {weekly.map((w, i) => (
          <span key={w.week} className="min-w-0 flex-1 text-center tabular-nums">
            {i % 4 === 0 || i === weekly.length - 1 ? shortDate(w.week, i18n.language) : ''}
          </span>
        ))}
      </div>
    </section>
  )
}

function StateBadge({ state }: { state: State }) {
  const { t } = useTranslation()
  if (state === 'finished')
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-gold">
        <Trophy size={14} aria-hidden />
        {t('tracker.state.finished')}
      </span>
    )
  return <span className="text-xs text-muted">{t(`tracker.state.${state}`)}</span>
}

function SeriesRow({ row }: { row: Row }) {
  const { t, i18n } = useTranslation()
  let detail = t('tracker.unknownDetail')
  if (row.unwatched)
    detail = t('tracker.missing', {
      count: row.unwatched,
      next: row.next ? `S${pad(row.next.season)}E${pad(row.next.episode)}` : '–',
    })
  else if (row.unwatched === 0) detail = t('tracker.nothingMissing')
  return (
    <li className="flex gap-3 rounded-card border border-line bg-surface p-3">
      <Poster url={row.poster_url} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <Link to={`/series/${row.series_id}`} className="font-medium hover:text-accent">
            {row.title}
          </Link>
          <StateBadge state={row.state} />
        </div>
        <p className="text-sm">{detail}</p>
        <p className="text-xs text-muted">
          {row.last_watched
            ? t('tracker.watchedLast', {
                count: row.watched,
                when: relativeTime(row.last_watched, i18n.language),
              })
            : t('tracker.watched', { count: row.watched })}
        </p>
      </div>
    </li>
  )
}

/** What the selected media-server users watched, and what is still unwatched. */
export function WatchTrackerPage() {
  const { t } = useTranslation()
  const [user, setUser] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [sort, setSort] = useState<Sort>('recent')
  const userArg = user ? `user=${user}` : ''
  const stats = useQuery({
    queryKey: ['watch-stats', user],
    queryFn: () => apiFetch<Stats>(`/api/v1/watch/stats${userArg ? `?${userArg}` : ''}`),
  })
  const params = `state=${filter}&sort=${sort}${userArg ? `&${userArg}` : ''}`
  const rows = useQuery({
    queryKey: ['watch-series', params],
    queryFn: () => apiFetch<Row[]>(`/api/v1/watch/series?${params}`),
  })
  const error = stats.error ?? rows.error
  if (error)
    return (
      <p role="alert" className="text-sm text-bad">
        {errorText(t, error)}
      </p>
    )
  const s = stats.data
  if (!s) return null
  if (!s.users.length)
    return (
      <>
        <PageTitle>{t('tracker.title')}</PageTitle>
        <EmptyState title={t('tracker.emptyTitle')}>
          {t('tracker.empty')}{' '}
          <Link to="/settings" className="text-accent underline">
            {t('nav.settings')}
          </Link>
        </EmptyState>
      </>
    )
  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <PageTitle>{t('tracker.title')}</PageTitle>
        <select
          aria-label={t('tracker.user')}
          value={user}
          onChange={(e) => setUser(e.target.value)}
          className={SELECT}
        >
          <option value="">{t('tracker.everyone')}</option>
          {s.users.map((u) => (
            <option key={u.id} value={u.id}>
              {s.users.filter((o) => o.name === u.name).length > 1
                ? `${u.name} (${u.server})`
                : u.name}
            </option>
          ))}
        </select>
      </div>
      <div className="grid gap-4 min-[1400px]:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="grid grid-cols-2 gap-3 min-[700px]:grid-cols-4 min-[1400px]:grid-cols-2">
          <Tile
            label={t('tracker.total')}
            value={String(s.episodes)}
            hint={t('tracker.hours', { count: Math.round(s.minutes / 60) })}
          />
          <Tile label={t('tracker.thisWeek')} value={String(s.this_week)} />
          <Tile label={t('tracker.thisMonth')} value={String(s.this_month)} />
          <Tile
            label={t('tracker.started')}
            value={String(s.series.started)}
            hint={t('tracker.startedHint', {
              behind: s.series.behind,
              finished: s.series.finished,
            })}
          />
        </div>
        <WeeklyChart weekly={s.weekly} />
      </div>
      {s.undated > 0 && (
        <p className="mt-2 text-xs text-muted">{t('tracker.undated', { count: s.undated })}</p>
      )}
      <section aria-labelledby="missing" className="mt-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 id="missing" className="font-display text-lg font-semibold">
            {t('tracker.missingTitle')}
          </h2>
          <select
            aria-label={t('tracker.sort')}
            value={sort}
            onChange={(e) => setSort(e.target.value as Sort)}
            className={SELECT}
          >
            {SORTS.map((option) => (
              <option key={option} value={option}>
                {t(`tracker.sorts.${option}`)}
              </option>
            ))}
          </select>
        </div>
        <div role="group" aria-label={t('tracker.filter')} className="mb-4 flex flex-wrap gap-2">
          {FILTERS.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={filter === option}
              onClick={() => setFilter(option)}
              className={`rounded-control border px-3 py-1 text-sm ${filter === option ? 'border-accent text-ink' : 'border-line text-muted hover:text-ink'}`}
            >
              {t(`tracker.filters.${option}`, {
                count: option === 'all' ? s.series.started : s.series[option],
              })}
            </button>
          ))}
        </div>
        {rows.data?.length === 0 && <p className="text-sm text-muted">{t('tracker.none')}</p>}
        <ul className="grid gap-2 min-[1400px]:grid-cols-2">
          {rows.data?.map((row) => (
            <SeriesRow key={row.series_id} row={row} />
          ))}
        </ul>
      </section>
    </>
  )
}
