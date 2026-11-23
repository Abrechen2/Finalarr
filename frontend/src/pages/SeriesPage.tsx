import { Search } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router'
import { EmptyState, PageTitle } from '../components/EmptyState'
import { FollowToggle } from '../components/FollowToggle'
import { Poster } from '../components/Poster'
import { SeasonProgress } from '../components/SeasonProgress'
import { errorKey } from '../lib/api'
import {
  type SeriesFilter,
  useFollowMonitored,
  useSeriesList,
  useSeriesPatch,
  useSeriesTags,
} from '../lib/series'
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

const WATCH = [
  ['', 'series.watchAll'],
  ['started', 'series.watchStarted'],
  ['behind', 'series.watchBehind'],
  ['caught_up', 'series.watchCaughtUp'],
] as const
const FOLLOW = [
  ['', 'series.followModeAll'],
  ['auto', 'series.followModeAuto'],
  ['always', 'series.followModeAlways'],
  ['never', 'series.followModeNever'],
] as const

function pick<T extends string>(
  value: string | null,
  options: readonly (readonly [T, string])[],
): T {
  return (options.find(([option]) => option === value)?.[0] ?? options[0][0]) as T
}

function readFilter(params: URLSearchParams): SeriesFilter {
  const followed = params.get('followed')
  const type = params.get('type')
  return {
    q: params.get('q') ?? '',
    followed: followed === 'true' || followed === 'false' ? followed : '',
    type: type === 'anime' || type === 'standard' ? type : '',
    watch: pick(params.get('watch'), WATCH),
    follow: pick(params.get('follow'), FOLLOW),
  }
}

function FilterSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: readonly (readonly [string, string])[]
  value: string
  onChange: (value: string) => void
}) {
  const { t } = useTranslation()
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-card border border-line bg-bg px-2 py-1.5 text-sm"
    >
      {options.map(([option, key]) => (
        <option key={option} value={option}>
          {t(key)}
        </option>
      ))}
    </select>
  )
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
              {series.followed && series.anilist_resolution === 'unresolved' && (
                <span
                  title={t('anilist.missingHint')}
                  className="ml-2 rounded-card border border-warn px-1.5 text-warn"
                >
                  {t('anilist.missing')}
                </span>
              )}
              {(series.anilist_resolution === 'auto' || series.anilist_resolution === 'manual') && (
                <span className="ml-2 rounded-card border border-line px-1.5">
                  {t('anilist.badge')}
                </span>
              )}
              {series.followed && series.follow_mode === 'auto' && (
                <span className="ml-2 rounded-card border border-line px-1.5">
                  {t('watch.badgeAuto')}
                </span>
              )}
              {Boolean(series.watched) && (
                <span className="ml-2 rounded-card border border-line px-1.5">
                  {t('watch.badgeWatched', { count: series.watched })}
                </span>
              )}
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
  const tags = useSeriesTags()
  const [tag, setTag] = useState('')
  const items = list.data?.pages.flatMap((page) => page.items) ?? []
  const filtered = Boolean(
    filter.q || filter.followed || filter.type || filter.watch || filter.follow,
  )

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
        <div className="flex flex-wrap items-center gap-2">
          {(tags.data?.length ?? 0) > 0 && (
            <select
              aria-label={t('series.tag')}
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              className="rounded-card border border-line bg-bg px-2 py-1.5 text-sm"
            >
              <option value="">{t('series.tagAll')}</option>
              {tags.data?.map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={() => followAll.mutate(tag || undefined)}
            disabled={followAll.isPending}
            className="rounded-control bg-accent px-3 py-1.5 text-sm font-bold text-on-accent disabled:opacity-60"
          >
            {tag ? t('series.followTag') : t('series.followAll')}
          </button>
        </div>
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
        <FilterSelect
          label={t('series.watchAll')}
          options={WATCH}
          value={filter.watch ?? ''}
          onChange={(v) => update('watch', v)}
        />
        <FilterSelect
          label={t('series.followModeAll')}
          options={FOLLOW}
          value={filter.follow ?? ''}
          onChange={(v) => update('follow', v)}
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
      <ul className="grid gap-2 min-[1400px]:grid-cols-2">
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
