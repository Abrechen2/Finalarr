import { ArrowLeft, ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { PageTitle } from '../components/EmptyState'
import { AnilistPicker } from '../components/AnilistPicker'
import { SeasonCheck } from '../components/SeasonCheck'
import { SeasonParts } from '../components/SeasonParts'
import { SeriesNews } from '../components/SeriesNews'
import { SeasonOverride } from '../components/SeasonOverride'
import { Toggle } from '../components/Toggle'
import { EpisodeGrid } from '../components/EpisodeGrid'
import { FollowToggle } from '../components/FollowToggle'
import { Poster } from '../components/Poster'
import { StateBadge } from '../components/StateBadge'
import { errorKey } from '../lib/api'
import { useSeriesDetail, useSeriesPatch } from '../lib/series'
import type { SeasonDetail, SeriesDetail } from '../lib/types'

function SeasonSection({ series, season }: { series: SeriesDetail; season: SeasonDetail }) {
  const { t, i18n } = useTranslation()
  const title = season.number === 0 ? t('season.specials') : t('season.title', { n: season.number })
  return (
    <section className="rounded-card border border-line bg-surface p-4">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h2 className="font-display font-semibold">{title}</h2>
        <StateBadge state={season.state} disputed={season.disputed} />
        <span className="text-sm font-bold">
          {season.have}/{season.expected ?? '?'}
        </span>
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
          {t('season.disputed', { sonarr: season.episodes.length, anilist: season.anilist_count })}
        </p>
      )}
      {season.state === 'unknown' && season.episodes.length === 0 && (
        <p className="mb-3 text-sm text-muted">
          {t('season.tvdbMissing')}
          {season.anilist_start &&
            ` ${t('anilist.startsOn', { date: new Date(season.anilist_start).toLocaleDateString(i18n.language === 'en' ? 'en-GB' : 'de-DE') })}`}
        </p>
      )}
      {season.episodes.length > 0 && (
        <EpisodeGrid
          season={season.number}
          episodes={season.episodes}
          partStarts={season.parts.slice(1).map((p) => p.from)}
        />
      )}
      <SeasonParts seriesId={series.id} season={season} />
      {series.followed && series.series_type === 'anime' && season.number > 0 && (
        <AnilistPicker seriesId={series.id} seriesTitle={series.title} season={season} />
      )}
      {series.followed && season.number > 0 && (
        <SeasonOverride seriesId={series.id} season={season} />
      )}
      {series.followed && <SeasonCheck seasonId={season.id} title={series.title} />}
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
      <div className="mb-6 flex flex-wrap gap-4">
        <Poster url={series.poster_url} size="lg" />
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <PageTitle>{series.title}</PageTitle>
          <p className="-mt-4 text-sm text-muted">
            {[
              series.year,
              series.series_type === 'anime' ? t('series.typeAnime') : t('series.typeStandard'),
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
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
      <SeriesNews seriesId={series.id} />
      <div className="flex flex-col gap-3">
        {seasons.map((season) => (
          <SeasonSection key={season.id} series={series} season={season} />
        ))}
      </div>
    </>
  )
}
