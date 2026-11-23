import { ArrowLeft, ExternalLink, MoreHorizontal } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { PageTitle } from '../components/EmptyState'
import { AnilistPicker } from '../components/AnilistPicker'
import { SeasonCheck } from '../components/SeasonCheck'
import { SeasonParts } from '../components/SeasonParts'
import { SeriesExtras } from '../components/SeriesExtras'
import { SeriesNews } from '../components/SeriesNews'
import { WaitingCard } from '../components/WaitingCard'
import { WatchPanel } from '../components/WatchPanel'
import { SeasonOverride } from '../components/SeasonOverride'
import { Toggle } from '../components/Toggle'
import { CountSources } from '../components/CountSources'
import { WatchCorrector } from '../components/WatchCorrector'
import { FollowToggle } from '../components/FollowToggle'
import { Poster } from '../components/Poster'
import { StateBadge } from '../components/StateBadge'
import { errorKey } from '../lib/api'
import { useSeriesDetail, useSeriesPatch } from '../lib/series'
import type { SeasonDetail, SeriesDetail, SeriesDetails } from '../lib/types'

const NO_DETAILS: SeriesDetails = {
  overview: '',
  network: '',
  runtime: null,
  genres: [],
  fanart_url: null,
}

function SeasonSection({ series, season }: { series: SeriesDetail; season: SeasonDetail }) {
  const { t, i18n } = useTranslation()
  const title = season.number === 0 ? t('season.specials') : t('season.title', { n: season.number })
  const [menuOpen, setMenuOpen] = useState(false)
  return (
    <section className="rounded-card border border-line bg-surface p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h2 className="font-display font-semibold">{title}</h2>
        <StateBadge state={season.state} disputed={season.disputed} />
        <span className="text-sm font-bold">
          {season.have}/{season.expected ?? '?'}
        </span>
        {series.followed && (
          <button
            type="button"
            aria-label={t('season.menu', { title })}
            aria-expanded={menuOpen}
            aria-controls={`season-menu-${season.id}`}
            onClick={() => setMenuOpen(!menuOpen)}
            className={`ml-auto rounded-control border px-1.5 py-0.5 ${menuOpen ? 'border-accent text-ink' : 'border-transparent text-muted hover:text-ink'}`}
          >
            <MoreHorizontal size={18} aria-hidden="true" />
          </button>
        )}
      </div>
      <p className="mb-3 text-sm text-muted">
        {season.expected && season.expected_source
          ? t('season.expected', {
              n: season.expected,
              source: t(`season.source.${season.expected_source}`),
            })
          : t('season.expectedUnknown')}
      </p>
      {season.disputed && (
        <p role="note" className="mb-3 rounded-card border border-bad px-3 py-2 text-sm text-bad">
          {season.anilist_count === null && season.external_count
            ? t('season.disputedExternal', {
                sonarr: season.episodes.length,
                other: season.external_count,
                source: t(`season.source.${season.external_source ?? 'tvmaze'}`),
              })
            : t('season.disputed', {
                sonarr: season.episodes.length,
                anilist: season.anilist_count,
              })}
        </p>
      )}
      {season.state === 'unknown' && season.episodes.length === 0 && (
        <p className="mb-3 text-sm text-muted">
          {t('season.tvdbMissing')}
          {season.anilist_start &&
            ` ${t('anilist.startsOn', { date: new Date(season.anilist_start).toLocaleDateString(i18n.language === 'en' ? 'en-GB' : 'de-DE') })}`}
        </p>
      )}
      {season.episodes.length > 0 && <WatchCorrector series={series} season={season} />}
      {season.number > 0 && <CountSources season={season} />}
      <SeasonParts seriesId={series.id} season={season} />
      {series.followed && series.series_type === 'anime' && season.number > 0 && (
        <AnilistPicker seriesId={series.id} seriesTitle={series.title} season={season} />
      )}
      {menuOpen && (
        <div
          id={`season-menu-${season.id}`}
          className="mt-3 flex flex-col gap-3 rounded-card border border-line p-3"
        >
          {season.number > 0 && <SeasonOverride seriesId={series.id} season={season} />}
          <SeasonCheck seasonId={season.id} title={series.title} />
        </div>
      )}
    </section>
  )
}

export function SeriesDetailPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const detail = useSeriesDetail(id)
  const patch = useSeriesPatch()

  if (detail.isError) {
    return (
      <p role="alert" className="text-sm text-bad">
        {t(errorKey(detail.error))}
      </p>
    )
  }
  if (!detail.data) return null
  const series = detail.data
  const details = series.details ?? NO_DETAILS
  const seasons = [...series.seasons].sort(
    (a, b) => (a.number === 0 ? 1 : 0) - (b.number === 0 ? 1 : 0) || b.number - a.number,
  )

  return (
    <>
      <Link
        to="/series"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"
      >
        <ArrowLeft size={16} aria-hidden="true" />
        {t('series.back')}
      </Link>
      {details.fanart_url && (
        <img
          src={details.fanart_url}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          className="mb-4 h-32 w-full rounded-card border border-line object-cover opacity-60 sm:h-44"
        />
      )}
      <div className="mb-6 flex flex-wrap gap-4">
        <Poster url={series.poster_url} size="lg" />
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <PageTitle>{series.title}</PageTitle>
          <p className="-mt-4 text-sm text-muted">
            {[
              series.year,
              series.series_type === 'anime' ? t('series.typeAnime') : t('series.typeStandard'),
              details.network,
              details.runtime && t('series.runtime', { n: details.runtime }),
              details.genres.slice(0, 3).join(', '),
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
          {details.overview && <p className="max-w-prose text-sm">{details.overview}</p>}
          <div className="flex flex-wrap gap-2">
            <FollowToggle
              followed={series.followed}
              busy={patch.isPending}
              onChange={(followed) => patch.mutate({ id: series.id, followed })}
            />
            <a
              href={series.sonarr_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-card border border-line px-3 py-1.5 text-sm text-muted hover:text-ink"
            >
              <ExternalLink size={16} aria-hidden="true" />
              {t('series.openInSonarr')}
            </a>
          </div>
          {!series.followed && <p className="text-sm text-muted">{t('season.notFollowed')}</p>}
          {series.followed && (
            <fieldset>
              <legend className="text-xs text-muted">{t('rules.series')}</legend>
              <Toggle
                label={t('rules.includeSpecials')}
                checked={series.include_specials}
                disabled={patch.isPending}
                onChange={(include_specials) => patch.mutate({ id: series.id, include_specials })}
              />
              <Toggle
                label={t('rules.respectMonitoring')}
                checked={series.respect_monitoring}
                disabled={patch.isPending}
                onChange={(respect_monitoring) =>
                  patch.mutate({ id: series.id, respect_monitoring })
                }
              />
              <Toggle
                label={t('calendar.seriesSwitch')}
                checked={series.calendar}
                disabled={patch.isPending}
                onChange={(calendar) => patch.mutate({ id: series.id, calendar })}
              />
            </fieldset>
          )}
        </div>
      </div>
      {/* Wide screens: what you wait for and watch on the left, news beside it. */}
      <div className="min-[1400px]:grid min-[1400px]:grid-cols-2 min-[1400px]:gap-4">
        <div>
          <WaitingCard waiting={series.waiting} />
          <WatchPanel series={series} />
          <SeriesExtras seriesId={series.id} title={series.title} />
        </div>
        <SeriesNews seriesId={series.id} />
      </div>
      <div className="flex flex-col gap-3">
        {seasons.map((season) => (
          <SeasonSection key={season.id} series={series} season={season} />
        ))}
      </div>
    </>
  )
}
