import { Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'
import { EmptyState, PageTitle } from '../components/EmptyState'
import { FollowToggle } from '../components/FollowToggle'
import { Poster } from '../components/Poster'
import { SeasonProgress } from '../components/SeasonProgress'
import { errorKey } from '../lib/api'
import { type SeriesFilter, useFollowMonitored, useSeriesList, useSeriesPatch } from '../lib/series'
import type { SeriesSummary } from '../lib/types'

const FOLLOWED = [
  ['', 'series.filterAll'],
  ['true', 'series.filterFollowed'],
  ['false', 'series.filterNotFollowed'],
] as const
const TYPES = [
  ['', 'series.typeAll'],
  ['anime', 'series.typeAnime'],
  ['standard', 'series.typeStandard'],
] as const

function readFilter(params: URLSearchParams): SeriesFilter {
  const followed = params.get('followed')
  const type = params.get('type')
  return {
    q: params.get('q') ?? '',
    followed: followed === 'true' || followed === 'false' ? followed : '',
    type: type === 'anime' || type === 'standard' ? type : '',
  }
}

function SeriesRow({ series }: { series: SeriesSummary }) {
  const { t } = useTranslation()
  const patch = useSeriesPatch()
  const seasons = series.seasons.filter((s) => s.number > 0 && s.expected !== null)
  return (
    <li className="flex gap-4 rounded-card border border-line bg-surface p-3">
      <Poster url={series.poster_url} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <Link to={`/series/${series.id}`} className="font-medium hover:text-accent">
              {series.title}
            </Link>
            <p className="text-xs text-muted">
              {[
                series.year,
                series.series_type === 'anime' ? t('series.typeAnime') : t('series.typeStandard'),
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
          <FollowToggle
            followed={series.followed}
            busy={patch.isPending}
            onChange={(followed) => patch.mutate({ id: series.id, followed })}
          />
        </div>
        {series.followed && seasons.length > 0 && (
          <div className="mt-3 flex flex-col gap-1.5">
            {seasons.slice(-2).map((season) => (
              <SeasonProgress key={season.id} season={season} />
            ))}
          </div>
        )}
      </div>
    </li>
  )
}

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: readonly (readonly [T, string])[]
  value: T
  onChange: (value: T) => void
}) {
  const { t } = useTranslation()
  return (
    <div
      role="group"
      aria-label={label}
      className="flex overflow-hidden rounded-card border border-line"
    >
      {options.map(([option, key]) => (
        <button
          key={option}
          type="button"
          aria-pressed={value === option}
          onClick={() => onChange(option)}
          className={`px-3 py-1.5 text-sm ${value === option ? 'bg-surface text-ink' : 'text-muted hover:text-ink'}`}
        >
          {t(key)}
        </button>
      ))}
    </div>
  )
}

export function SeriesPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const filter = readFilter(params)
  const list = useSeriesList(filter)
  const followAll = useFollowMonitored()
  const items = list.data?.pages.flatMap((page) => page.items) ?? []
  const filtered = Boolean(filter.q || filter.followed || filter.type)

  function update(key: keyof SeriesFilter, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <PageTitle>{t('series.title')}</PageTitle>
        <button
          type="button"
          onClick={() => followAll.mutate()}
          disabled={followAll.isPending}
          className="rounded-card bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
        >
          {t('series.followAll')}
        </button>
      </div>
      {followAll.isSuccess && (
        <p role="status" className="mb-4 text-sm text-ok">
          {t('series.followAllDone', { count: followAll.data.followed })}
        </p>
      )}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <label className="flex min-w-56 flex-1 items-center gap-2 rounded-card border border-line bg-bg px-3 py-1.5">
          <Search size={16} aria-hidden="true" className="text-muted" />
          <span className="sr-only">{t('series.search')}</span>
          <input
            type="search"
            value={filter.q}
            placeholder={t('series.search')}
            onChange={(e) => update('q', e.target.value)}
            className="w-full bg-transparent text-sm outline-none"
          />
        </label>
        <Segmented
          label={t('series.filterFollowed')}
          options={FOLLOWED}
          value={filter.followed}
          onChange={(v) => update('followed', v)}
        />
        <Segmented
          label={t('series.typeAll')}
          options={TYPES}
          value={filter.type}
          onChange={(v) => update('type', v)}
        />
      </div>
      {list.isError && (
        <p role="alert" className="text-sm text-bad">
          {t(errorKey(list.error))}
        </p>
      )}
      {list.isSuccess &&
        items.length === 0 &&
        (filtered ? (
          <p className="text-sm text-muted">{t('series.noMatch')}</p>
        ) : (
          <EmptyState title={t('series.emptyTitle')}>{t('series.emptyBody')}</EmptyState>
        ))}
      <ul className="flex flex-col gap-2">
        {items.map((series) => (
          <SeriesRow key={series.id} series={series} />
        ))}
      </ul>
      {list.hasNextPage && (
        <button
          type="button"
          onClick={() => void list.fetchNextPage()}
          disabled={list.isFetchingNextPage}
          className="mt-4 rounded-card border border-line px-4 py-2 text-sm text-muted hover:text-ink"
        >
          {t('series.loadMore')}
        </button>
      )}
    </>
  )
}
