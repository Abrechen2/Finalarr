import { useQuery } from '@tanstack/react-query'
import { CalendarClock, Play, Tv } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../lib/api'
import { pad } from '../lib/episodes'
import { airTime, relativeTime } from '../lib/format'
import type { SeriesExtras as Extras } from '../lib/types'

const SOURCE_NAMES = { sonarr: 'Sonarr', anilist: 'AniList', tvmaze: 'TVmaze' } as const
const CHIP = 'inline-block rounded-full border border-line px-2.5 py-0.5 text-sm'

const CREDIT_NAMES: Record<string, string> = { ...SOURCE_NAMES, tmdb: 'TMDB' }

/** "per TVmaze", linked to the source page when there is one (TVmaze's CC BY-SA asks for it). */
function SourceCredit({ source, links }: { source: string; links?: Record<string, string> }) {
  const { t } = useTranslation()
  const name = CREDIT_NAMES[source] ?? source
  const href = links?.[source]
  const text = t('extras.source', { source: name })
  return href ? (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      title={t('extras.onSource', { source: name })}
      className="text-xs text-muted underline hover:text-accent"
    >
      {text}
    </a>
  ) : (
    <span className="text-xs text-muted">{text}</span>
  )
}

/** Click-to-load: nothing is requested from YouTube before the click. */
function Trailer({ id, title }: { id: string; title: string }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  if (open) {
    return (
      <iframe
        className="aspect-video w-full max-w-2xl rounded-card border border-line"
        src={`https://www.youtube-nocookie.com/embed/${encodeURIComponent(id)}?autoplay=1`}
        title={t('extras.trailerTitle', { title })}
        allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
        referrerPolicy="strict-origin-when-cross-origin"
      />
    )
  }
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-control border border-line px-3 py-1.5 text-sm hover:border-accent"
      >
        <Play size={16} aria-hidden="true" />
        {t('extras.trailer')}
      </button>
      <p className="mt-1 text-xs text-muted">{t('extras.trailerNote')}</p>
    </div>
  )
}

function Dub({ dub }: { dub: NonNullable<Extras['dub']> }) {
  const { t, i18n } = useTranslation()
  const when = (iso: string) => airTime(iso, i18n.language)
  const parts = [
    dub.delayed_until && t('extras.dubDelayed', { when: when(dub.delayed_until) }),
    dub.next && t('extras.dubNext', { when: when(dub.next) }),
    !dub.next && dub.premiere && t('extras.dubPremiere', { when: when(dub.premiere) }),
    dub.delay_note,
  ].filter(Boolean)
  if (!parts.length) return null
  return (
    <p className="text-sm">
      <span className="font-bold">{t('extras.dub')}: </span>
      {parts.join(' · ')}{' '}
      <a
        href={dub.url}
        target="_blank"
        rel="noreferrer noopener"
        className="text-xs text-muted hover:text-accent"
      >
        {t('extras.dubSource')}
      </a>
    </p>
  )
}

/** Next episode with countdown, channel, where to watch, English dub and trailer. */
export function SeriesExtras({ seriesId, title }: { seriesId: number; title: string }) {
  const { t, i18n } = useTranslation()
  const extras = useQuery({
    queryKey: ['series', 'extras', seriesId],
    queryFn: () => apiFetch<Extras>(`/api/v1/series/${seriesId}/extras`),
    staleTime: 10 * 60_000,
  })
  const data = extras.data
  if (!data) return null
  const next = data.next_episode
  const empty = !next && !data.channel && !data.watch.length && !data.trailer && !data.dub
  if (empty && !data.errors.length) return null
  const relative = next ? relativeTime(next.at, i18n.language) : ''
  return (
    <section className="mb-4 flex flex-col gap-3 rounded-card border border-line bg-surface p-4">
      {next && (
        <p className="flex flex-wrap items-baseline gap-x-2">
          <CalendarClock size={18} aria-hidden="true" className="self-center text-accent" />
          <span className="font-bold">
            {next.season !== null
              ? t('extras.next', { s: pad(next.season), e: pad(next.episode), relative })
              : t('extras.nextNoSeason', { e: pad(next.episode), relative })}
          </span>
          <span className="text-sm">{airTime(next.at, i18n.language)}</span>
          <SourceCredit source={next.source} links={data.source_links} />
        </p>
      )}
      {data.channel && (
        <p className="flex items-center gap-2 text-sm">
          <Tv size={16} aria-hidden="true" className="text-muted" />
          {t('extras.channel', { channel: data.channel })}
          {data.source_links?.tvmaze && <SourceCredit source="tvmaze" links={data.source_links} />}
        </p>
      )}
      {data.watch.length > 0 && (
        <div>
          <p className="mb-1 text-xs text-muted">{t('extras.watch')}</p>
          <ul className="flex flex-wrap gap-1.5">
            {data.watch.map((w) => (
              <li key={w.name}>
                {w.url ? (
                  <a
                    href={w.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className={`${CHIP} hover:border-accent`}
                  >
                    {w.name}
                  </a>
                ) : (
                  <span className={CHIP}>{w.name}</span>
                )}
              </li>
            ))}
          </ul>
          {data.watch_region && data.watch.some((w) => w.source === 'tmdb') && (
            <p className="mt-1 text-xs text-muted">
              {t('extras.watchRegion', { region: data.watch_region })}{' '}
              {data.source_links?.tmdb && <SourceCredit source="tmdb" links={data.source_links} />}
            </p>
          )}
        </div>
      )}
      {data.dub && <Dub dub={data.dub} />}
      {data.trailer && <Trailer id={data.trailer.youtube_id} title={title} />}
      {data.errors.length > 0 && <p className="text-xs text-muted">{t('extras.errors')}</p>}
    </section>
  )
}
